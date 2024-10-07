from setuptools import setup, find_packages

setup(
    name='Dobby-CLI',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'openai',
        'InquirerPy',
    ],
    entry_points={
        'console_scripts': [
            'dobby = main:main',
        ],
    },
)
