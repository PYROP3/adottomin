import os
from dotenv import load_dotenv

load_dotenv()

def pint(property:str, required:bool=True):
    prop = os.getenv(property)
    if required and not prop:
        raise RuntimeError(f"Missing required env variable {property}")
    return prop and int(prop)

def plist(property:str, required:bool=True):
    aux = os.getenv(property)
    if required and not aux:
        raise RuntimeError(f"Missing required env variable {property}")
    return [] if not aux else [elem and int(elem) for elem in aux.split('.')]

def pstr(property:str, required:bool=True, default:str=None):
    prop = os.getenv(property)
    if required and not prop and not default:
        raise RuntimeError(f"Missing required env variable {property}")
    return prop or default
