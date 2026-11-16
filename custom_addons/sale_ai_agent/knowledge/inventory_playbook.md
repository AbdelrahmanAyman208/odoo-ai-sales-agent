# Inventory & Warehouse Architecture Playbook

## 1. Storage Location Topology
- **Systematic Hierarchical Naming**: `<Warehouse>/<Zone>/<Aisle or Rack>-<Level>`
  - Example: `WH/Stock/Zone-A/R1-L1`
- **Location Usages**:
  - `internal`: Usable stock zones, racks, display showrooms.
  - `transit`: Inter-warehouse shipments.
  - `supplier`: Vendor goods receipt.
  - `customer`: Dispatched shipments.
  - `inventory`: Cycle counting variance adjustments.
  - `production`: Work-in-progress staging.

## 2. Replenishment Mathematics
- **Average Daily Demand ($ADD$)**:
  $$\text{ADD} = \frac{\sum \text{Delivered Units in last 90 days}}{90}$$
- **Reorder Point (Minimum Qty)**:
  $$\text{Min} = (\text{ADD} \times \text{Lead Time Days}) + \text{Safety Buffer}$$
- **Target Stock (Maximum Qty)**:
  $$\text{Max} = \text{Min} \times 2.5$$
