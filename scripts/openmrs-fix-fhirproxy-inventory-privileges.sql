-- Additive FHIR Proxy inventory/price grants (does not replace existing role privileges).
-- Required so the order basket can call InventoryItem / ChargeItemDefinition via fhirproxy.
-- Idempotent. Apply on existing instances after enabling fhirproxy.

INSERT IGNORE INTO privilege (privilege, description, uuid) VALUES
  ('Get ChargeItemDefinition', 'Able to get ChargeItemDefinitions', '9b8cfdec-1788-4cb5-9a2e-c14852650655'),
  ('Get InventoryItem', 'Able to get InventoryItems', '8578353f-0dea-4e12-803e-00d75627fab7');

INSERT IGNORE INTO role (role, uuid, description)
VALUES (
  'FHIR Proxy Access',
  'b3d7e91c-4a2f-5c18-8e6d-0a1c2e3f4b50',
  'Read Odoo ChargeItemDefinition and InventoryItem via fhirproxy (order-basket stock/price)'
);

INSERT IGNORE INTO role_role (parent_role, child_role) VALUES
  ('Provider', 'FHIR Proxy Access'),
  ('Privilege Level: Full', 'FHIR Proxy Access'),
  ('Privilege Level: High', 'FHIR Proxy Access'),
  ('Inventory Provider Access', 'FHIR Proxy Access');

INSERT IGNORE INTO role_privilege (role, privilege) VALUES
  ('FHIR Proxy Access', 'Get InventoryItem'),
  ('FHIR Proxy Access', 'Get ChargeItemDefinition'),
  ('Provider', 'Get InventoryItem'),
  ('Provider', 'Get ChargeItemDefinition'),
  ('System Developer', 'Get InventoryItem'),
  ('System Developer', 'Get ChargeItemDefinition'),
  ('Privilege Level: Full', 'Get InventoryItem'),
  ('Privilege Level: Full', 'Get ChargeItemDefinition'),
  ('Inventory Provider Access', 'Get InventoryItem'),
  ('Inventory Provider Access', 'Get ChargeItemDefinition');
