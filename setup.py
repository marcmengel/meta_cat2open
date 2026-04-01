from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

def wrap_find_packages(*args, **kwargs):
    res = find_packages(*args, **kwargs)
    print(f"find_packages returns {res}")
    return res

# Get the long description from the README file
long_description = (here / "README.md").read_text(encoding="utf-8")
setup(
    name = "metacat2amsc",
    version = "0.0.1",
    long_description_content_type="text/markdown",
    author= "Marc Mengel", 
    author_email="mengel@fnal.gov",
    classifiers = [
      "Development Status :: 3 - Alpha",
      # Indicate who your project is intended for
      "Intended Audience :: Developers",
      "License :: OSI Approved :: Apache 2.0 License",
    ],
    package_dir={"": "metacat2amsc"}, 
    packages=["."],
    python_requires=">=3.6",
    install_requires=["metacat-client"],
    scripts=["metacat2amsc/c2o.py"]
)
