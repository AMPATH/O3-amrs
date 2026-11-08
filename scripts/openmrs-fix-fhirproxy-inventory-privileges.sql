-- Grant FHIR Proxy inventory/price privileges to clinical roles.
-- Required so the order basket can call InventoryItem / ChargeItemDefinition via fhirproxy.
-- Idempotent. Apply on existing instances after enabling fhirproxy.

INSERT IGNORE INTO role_role (parent_role, child_role) VALUES
  ('Provider', 'Inventory Provider Access'),
  ('Privilege Level: Full', 'Inventory Provider Access'),
  ('Privilege Level: High', 'Inventory Provider Access');

INSERT IGNORE INTO role_privilege (role, privilege) VALUES
  ('Provider', 'Get InventoryItem'),
  ('Provider', 'Get ChargeItemDefinition'),
  ('System Developer', 'Get InventoryItem'),
  ('System Developer', 'Get ChargeItemDefinition'),
  ('Privilege Level: Full', 'Get InventoryItem'),
  ('Privilege Level: Full', 'Get ChargeItemDefinition'),
  ('Inventory Provider Access', 'Get InventoryItem'),
  ('Inventory Provider Access', 'Get ChargeItemDefinition');
