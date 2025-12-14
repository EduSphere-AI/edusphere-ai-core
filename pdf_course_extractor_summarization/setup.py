
from setuptools import setup, find_packages

setup(
    name="pdf_course_extractor_summarization",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pymupdf",
        "pdfplumber",
        "pytesseract",
        "Pillow",
        "transformers",
        "torch",
        "tqdm",
        "scipy",
        "numpy"
    ],
    entry_points={
        'console_scripts': [
            'extract-course=pdf_course_extractor_summarization.main:main',
        ],
    },
)