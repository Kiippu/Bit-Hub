# This file is used by PythonAnywhere as the WSGI entry point.
# In PythonAnywhere dashboard: set this file path in your Web tab.
import sys
import os

# Replace 'yourusername' with your actual PythonAnywhere username
project_home = '/home/yourusername/bitcraft-hub'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from app import app as application
