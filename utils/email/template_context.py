import re




ALLOWED_TEMPLATE_VARIABLES = {
    "first_name",
    "username",
    "email",
    "site_domain",
    "unsubscribe_url",
}


def extract_template_variables(template_str):
    """
    Extracts all {{ variable }} occurrences from a template string.
    """
    return set(re.findall(r'{{\s*(\w+)\s*}}', template_str))


def validate_template_variables(template_str):
    """
    Validates that all template variables are from the allowed list.
    Raises ValueError if any unknown variables are found.
    """
    used_vars = extract_template_variables(template_str)
    invalid_vars = used_vars - ALLOWED_TEMPLATE_VARIABLES
    if invalid_vars:
        raise ValueError(f"Invalid template variables used: {', '.join(invalid_vars)}")
