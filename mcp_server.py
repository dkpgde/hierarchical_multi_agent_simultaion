import sys
import os
import logging

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(asctime)s - SERVER - %(message)s')
logger = logging.getLogger("SCM_Server")

sys.path.append(os.getcwd())

from mcp.server.fastmcp import FastMCP
try:
    from tools import get_part_id, get_stock_level, get_supplier_location, get_shipping_cost
except ImportError as e:
    logger.error(f"Failed to import tools: {e}")
    sys.exit(1)

mcp = FastMCP("SCM_Logistics_Server")


@mcp.tool()
def find_part_id(part_name: str) -> str:
    """
    Retrieves the technical Part ID for a given English part name (e.g., "ID-999" or an error message).
    USE THIS FIRST. You cannot check stock or location without an ID.
    
    Args:
        part_name: The common name of the part (e.g., "Engine", "Tire").
    """
    return get_part_id(part_name)

@mcp.tool()
def check_stock(part_id: str) -> str:
    """
    Checks the current inventory quantity for a specific Part ID.
    
    Args:
        part_id: The technical ID (must start with "ID-", e.g., "ID-100").
    """
    return get_stock_level(part_id)

@mcp.tool()
def find_supplier_city(part_id: str) -> str:
    """
    Finds the city where the supplier for a specific Part ID is located.
    
    Args:
        part_id: The technical ID (must start with "ID-", e.g., "ID-100").
    """
    return get_supplier_location(part_id)

@mcp.tool()
def calculate_shipping(city: str) -> str:
    """
    Calculates the shipping cost to transport items from a specific Supplier City.
    
    Args:
        city: The name of the city (e.g., "Stuttgart", "Berlin").
    """
    return get_shipping_cost(city)

if __name__ == "__main__":
    mcp.run()