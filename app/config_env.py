"""Public configuration names; legacy VMM settings remain supported."""
import os


def config_env(name, default=None):
    return os.environ.get('TENTACLE_'+name) or os.environ.get('VMM_'+name) or default
