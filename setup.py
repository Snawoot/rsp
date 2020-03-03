from setuptools import setup

from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(name='rsp',
      version='0.5.1',
      description='Rapid SSH Proxy',
      url='https://github.com/Snawoot/rsp',
      author='Vladislav Yarmak',
      author_email='vladislav-ex-src@vm-0.com',
      license='MIT',
      packages=['rsp'],
      python_requires='>=3.5.3',
      setup_requires=[
          'wheel',
      ],
      install_requires=[
          'asyncssh>=1.16.0',
      ],
      extras_require={
          'dev': [
              'setuptools>=38.6.0',
              'wheel>=0.31.0',
              'twine>=1.11.0',
          ],
          'uvloop': 'uvloop>=0.11.0',
      },
      entry_points={
          'console_scripts': [
              'rsp=rsp.__main__:main',
              'rsp-trust=rsp.trust:main',
              'rsp-keygen=rsp.keygen:main',
          ],
      },
      classifiers=[
          "Programming Language :: Python :: 3.5",
          "License :: OSI Approved :: MIT License",
          "Operating System :: OS Independent",
          "Development Status :: 4 - Beta",
          "Environment :: No Input/Output (Daemon)",
          "Intended Audience :: System Administrators",
          "Natural Language :: English",
          "Topic :: Internet",
          "Topic :: Security",
      ],
      long_description=long_description,
      long_description_content_type='text/markdown',
      zip_safe=True)
