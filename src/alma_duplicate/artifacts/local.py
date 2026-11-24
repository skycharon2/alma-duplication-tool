"""Immutable bundles in an operator-owned persistent local directory."""
import errno
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
from uuid import uuid4

from alma_duplicate.artifacts.base import Artifact, FILES, INPUT_FILES

_BUNDLE_FILES = FILES | INPUT_FILES


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class LocalArtifactStore:
    def __init__(self, root):
        self.root = Path(root).absolute()
        if self.root.is_symlink():
            raise ValueError('Artifact root must not be a symlink')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.root.is_dir():
            raise ValueError('Artifact root must be a directory')

    def put_bundle(self, files):
        if not files or set(files) - _BUNDLE_FILES.keys():
            raise ValueError('Unsupported artifact kinds')
        token = uuid4().hex
        staging, destination = self.root / ('.pending-' + token), self.root / token
        staging.mkdir(mode=0o700)
        records = []
        try:
            for kind, source in files.items():
                digest, size = hashlib.sha256(), 0
                filename = _BUNDLE_FILES[kind]
                fd = os.open(staging / filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'wb') as output, Path(source).open('rb') as stream:
                    while block := stream.read(1024 * 1024):
                        output.write(block)
                        digest.update(block)
                        size += len(block)
                    output.flush()
                    os.fsync(output.fileno())
                records.append(Artifact(kind, f'{token}/{filename}', digest.hexdigest(), size))
            _sync_directory(staging)
            # Random bundle IDs are never reused. The root is service-owned.
            staging.rename(destination)
            _sync_directory(self.root)
            return records
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    def _location(self, kind, storage_key):
        filename = _BUNDLE_FILES.get(kind)
        parts = storage_key.split('/')
        if (len(parts) != 2 or re.fullmatch('[0-9a-f]{32}', parts[0]) is None
                or parts[1] != filename):
            raise ValueError('Invalid artifact storage key')
        return parts[0], filename

    def remove(self, kind, storage_key):
        """Unlink an immutable artifact. Already-open POSIX streams stay valid."""
        bundle, filename = self._location(kind, storage_key)
        root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            try:
                bundle_fd = os.open(bundle, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                    dir_fd=root_fd)
            except FileNotFoundError:
                os.fsync(root_fd)
                return
            try:
                try:
                    os.unlink(filename, dir_fd=bundle_fd)
                except FileNotFoundError:
                    pass
                os.fsync(bundle_fd)
            finally:
                os.close(bundle_fd)
            try:
                os.rmdir(bundle, dir_fd=root_fd)
            except FileNotFoundError:
                pass
            except OSError as exc:
                if exc.errno != errno.ENOTEMPTY:
                    raise
            os.fsync(root_fd)
        finally:
            os.close(root_fd)

    def open_verified(self, artifact):
        bundle, filename = self._location(artifact.kind, artifact.storage_key)
        directory = self.root / bundle
        if directory.is_symlink():
            raise ValueError('Artifact bundle must not be a symlink')
        fd = os.open(directory / filename, os.O_RDONLY | os.O_NOFOLLOW)
        stream = os.fdopen(fd, 'rb')
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size != artifact.byte_size:
                raise ValueError('Artifact size or file type mismatch')
            if hashlib.file_digest(stream, 'sha256').hexdigest() != artifact.sha256:
                raise ValueError('Artifact digest mismatch')
            stream.seek(0)
            return stream
        except BaseException:
            stream.close()
            raise
