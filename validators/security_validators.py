from django.core.exceptions import ValidationError
import os

def validate_no_executable_file(value):
    ext = os.path.splitext(value.name)[1].lower()
    unsafe = [".exe", ".bat", ".sh", ".dll", ".com", ".msi", ".vbs", ".wsf", ".scr", ".py", ".php", ".js", ".jar"]
    if ext in unsafe:
        raise ValidationError("Executable files are not allowed.")
