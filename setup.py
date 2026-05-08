from setuptools import setup, find_packages


setup(
    name='watermark-tool',
    version='1.0.0',
    packages=find_packages(),
    install_requires=[
        'PySide6>=6.6.0',
        'opencv-python>=4.9.0',
        'numpy>=1.26.0'
    ],
    entry_points={
        'console_scripts': [
            'watermark-tool=src.main:main'
        ]
    }
)