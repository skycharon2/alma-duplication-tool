"""Explicit bounded resource overrides shared by Mosaic acquisition entrypoints."""
from dataclasses import dataclass


@dataclass(frozen=True)
class MosaicResourceLimits:
    max_download_bytes: int = 300_000_000
    max_weblog_bytes: int = 250_000_000
    max_expanded_bytes: int = 1_000_000_000

    def __post_init__(self):
        for name, ceiling in [('max_download_bytes', 1_000_000_000),
                              ('max_weblog_bytes', 1_000_000_000),
                              ('max_expanded_bytes', 10_000_000_000)]:
            value = getattr(self, name)
            if type(value) is not int or not 0 < value <= ceiling:
                raise ValueError(f'{name} must be an integer in 1..{ceiling}')


def add_resource_arguments(parser, prefix=''):
    for name, default in vars(MosaicResourceLimits()).items():
        parser.add_argument('--' + prefix + name.replace('_', '-'), type=int, default=default)


def resource_arguments(args, prefix=''):
    return MosaicResourceLimits(**{name: getattr(args, prefix + name)
                                  for name in vars(MosaicResourceLimits())})
