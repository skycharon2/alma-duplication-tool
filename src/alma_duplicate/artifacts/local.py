"""Immutable bundles in an operator-owned persistent local directory."""
import errno
import gzip
import hashlib
from contextlib import nullcontext
from io import BytesIO
import os
from pathlib import Path
import re
import shutil
import stat
from tempfile import TemporaryFile
from uuid import uuid4
import zlib

from alma_duplicate.artifacts.base import Artifact, FILES, INPUT_FILES

_BUNDLE_FILES = FILES | INPUT_FILES
_BLOCK_SIZE = 1024 * 1024
_COMPRESSION_MIN_SIZE = 64 * 1024
_COMPRESSED_INSPECTION = FILES['inspection'] + '.gz'
_COMPRESSED_REPORT = FILES['report'] + '.gz'


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class _ReportRanges:
    def __init__(self, stream, artifact):
        self.stream, self.artifact = stream, artifact
        blocks = artifact.report_blocks
        if (not blocks or len(blocks) != (artifact.byte_size + _BLOCK_SIZE - 1) // _BLOCK_SIZE
                or blocks[-1][0] != artifact.stored_byte_size):
            raise ValueError('Invalid compressed report index')
        self.cached_index = None
        self.cached_block = b''

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stream.close()

    def _block(self, index):
        if self.cached_index == index:
            return self.cached_block
        blocks = self.artifact.report_blocks
        end, digest = blocks[index]
        start = blocks[index - 1][0] if index else 0
        size = min(_BLOCK_SIZE, self.artifact.byte_size - index * _BLOCK_SIZE)
        if not 0 <= start < end <= self.artifact.stored_byte_size:
            raise ValueError('Invalid compressed report block range')
        self.stream.seek(start)
        try:
            with gzip.GzipFile(fileobj=BytesIO(self.stream.read(end - start))) as expanded:
                raw = expanded.read(size + 1)
        except (EOFError, zlib.error) as exc:
            raise ValueError('Invalid compressed report block') from exc
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Report block size or digest mismatch')
        self.cached_index, self.cached_block = index, raw
        return raw

    def read_range(self, offset, length):
        end = offset + length
        if not 0 <= offset <= end <= self.artifact.byte_size:
            raise ValueError('Invalid logical report range')
        result = bytearray()
        while offset < end:
            index, start = divmod(offset, _BLOCK_SIZE)
            count = min(end - offset, _BLOCK_SIZE - start)
            result.extend(self._block(index)[start:start + count])
            offset += count
        return result


class LocalArtifactStore:
    def __init__(self, root, *, compress_inspection=False, compress_reports=False):
        self.root = Path(root).absolute()
        self.compress_inspection = compress_inspection
        self.compress_reports = compress_reports
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
                compress = (self.compress_inspection and kind == 'inspection'
                            and Path(source).stat().st_size >= _COMPRESSION_MIN_SIZE)
                report_blocks = ([] if self.compress_reports and kind == 'report'
                                 and Path(source).stat().st_size >= _COMPRESSION_MIN_SIZE else None)
                if compress:
                    filename = _COMPRESSED_INSPECTION
                if report_blocks is not None:
                    filename = _COMPRESSED_REPORT
                fd = os.open(staging / filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'wb') as output, Path(source).open('rb') as stream:
                    writer = (gzip.GzipFile(filename='', mode='wb', compresslevel=1, fileobj=output, mtime=0)
                              if compress else nullcontext(output))
                    with writer as sink:
                        while block := stream.read(_BLOCK_SIZE):
                            if report_blocks is None:
                                sink.write(block)
                            else:
                                sink.write(gzip.compress(block, compresslevel=1, mtime=0))
                                report_blocks.append((output.tell(), hashlib.sha256(block).hexdigest()))
                            digest.update(block)
                            size += len(block)
                    output.flush()
                    os.fsync(output.fileno())
                    stored = output.tell() if compress or report_blocks is not None else None
                records.append(Artifact(kind, f'{token}/{filename}', digest.hexdigest(), size,
                                        stored, report_blocks))
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
        if kind == 'inspection' and parts[-1] == _COMPRESSED_INSPECTION:
            filename = _COMPRESSED_INSPECTION
        if kind == 'report' and parts[-1] == _COMPRESSED_REPORT:
            filename = _COMPRESSED_REPORT
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

    def _open_stored(self, artifact):
        bundle, filename = self._location(artifact.kind, artifact.storage_key)
        directory = self.root / bundle
        if directory.is_symlink():
            raise ValueError('Artifact bundle must not be a symlink')
        fd = os.open(directory / filename, os.O_RDONLY | os.O_NOFOLLOW)
        stream = os.fdopen(fd, 'rb')
        try:
            info = os.fstat(fd)
            compressed = filename in {_COMPRESSED_INSPECTION, _COMPRESSED_REPORT}
            expected_size = artifact.stored_byte_size if compressed else artifact.byte_size
            if not stat.S_ISREG(info.st_mode) or info.st_size != expected_size:
                raise ValueError('Artifact size or file type mismatch')
            return stream, compressed
        except BaseException:
            stream.close()
            raise

    def open_verified(self, artifact):
        stream, compressed = self._open_stored(artifact)
        try:
            if compressed:
                with stream:
                    return self._open_compressed(stream, artifact)
            if hashlib.file_digest(stream, 'sha256').hexdigest() != artifact.sha256:
                raise ValueError('Artifact digest mismatch')
            stream.seek(0)
            return stream
        except BaseException:
            stream.close()
            raise

    def open_report_ranges(self, artifact):
        """Open an indexed report for bounded context reads."""
        stream, compressed = self._open_stored(artifact)
        if not compressed or artifact.kind != 'report':
            stream.close()
            raise ValueError('Expected a compressed report')
        try:
            return _ReportRanges(stream, artifact)
        except BaseException:
            stream.close()
            raise

    def _open_compressed(self, stream, artifact):
        verified = TemporaryFile(mode='w+b')
        digest = hashlib.sha256()
        remaining = artifact.byte_size
        try:
            try:
                with gzip.GzipFile(fileobj=stream, mode='rb') as expanded:
                    while block := expanded.read(min(_BLOCK_SIZE, remaining + 1)):
                        remaining -= len(block)
                        if remaining < 0:
                            raise ValueError('Artifact size mismatch')
                        digest.update(block)
                        verified.write(block)
            except (EOFError, zlib.error) as exc:
                raise ValueError('Invalid compressed artifact') from exc
            if remaining or digest.hexdigest() != artifact.sha256:
                raise ValueError('Artifact digest or size mismatch')
            verified.seek(0)
            return verified
        except BaseException:
            verified.close()
            raise
