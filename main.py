import sys
import os

# Ensure the project root is in the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.app import Application

def main():
    """
    Entry point for Programita 2.
    """
    app = Application()
    app.run()

if __name__ == "__main__":
    main()
