import os

from distutils.core import setup

setup(name='gozbruh',
      version='1.1.3',
      description='Cross-platform and cross-machine file sync for ZBrush',
      author='Luma Pictures',
      url='lumapictures.com',
      platforms='Unix,OSX',
      packages=['gozbruh'],
      package_dir={'gozbruh': 'gozbruh'},
      package_data={'goghz': [os.path.join('gozbruh', '*.txt')]},
      scripts=[os.path.join('scripts', 'goz_config')]
      )
