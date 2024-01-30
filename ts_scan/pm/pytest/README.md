# Pytest

This directory houses the pytest scripts for the `pm` package. The tests are automatically run on GitHub for each new commit.

## Running pytest locally

1. Make sure you have pytest installed

    ```pip install pytest```

2. From the **top-level** directory (repo-level), run `python -m pytest`

    Just `pytest` **will not work** properly, as pytest cannot discover packages this way

## To create tests that apply to **all** scanner modules:

1. Edit the file `test_pm.py`
2. Define a function that starts with "test_"
3. Use assert statements to check whatever you want to check
4. If you define the parameter `scanner_class`, your function will be executed for each submodule 
    - `scanner_class` is a tuple as `(classname: str, class: *Scan)`

## To write tests for a **specific** scanner module:

1. Create a file called `test_<name>.py` in the pytest directory (this one)
2. Proceed as above, but **DON'T** use the scanner_class parameter, or your test will be executed for all submodules. Rather, hardcode the `*Scan` class you want to test into the script.