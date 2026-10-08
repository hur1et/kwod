"""Run the redacted cost observer under the production runtime identity."""
from kwod.production_costs import write_public

if __name__ == '__main__':
    write_public()
