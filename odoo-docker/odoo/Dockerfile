# Odoo image with Ozone configs and addons (from ozone-his/ozone).
# Build context must include: binaries/odoo/addons/, config/odoo/initializer_config/, config/odoo/config/odoo.conf
FROM mekomsolutions/odoo

ADD binaries/odoo/addons /mnt/extra-addons
ADD config/odoo/initializer_config /mnt/odoo_config
ADD config/odoo/config/odoo.conf /etc/properties/odoo.conf
