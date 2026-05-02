# Patch for odoo_initializer.utils.registry (Mekom).
#
# Upstream only assigns ``cursor`` / ``env`` when ``reg is None``. After the first
# ``start_init(cr)`` completes and commits, later registry loads pass a new ``cr``
# but the singleton keeps the old closed cursor → psycopg2.InterfaceError:
# Cursor already closed during CSV NO_UPDATE / _record_exist.
#
# Applied in odoo-docker/odoo/Dockerfile over odoo_initializer/utils/registry.py

import logging

import odoo

_logger = logging.getLogger(__name__)


class Registry(object):

    init = False
    reg = None
    cursor = None
    env = None

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Registry, cls).__new__(cls)
        return cls.instance

    def initialize(self, cr):
        """Always bind to the active registry-load cursor (never reuse a stale cursor)."""
        uid = odoo.SUPERUSER_ID
        self.env = odoo.api.Environment(cr, uid, {})
        self.reg = self.env.registry
        self.cursor = cr

    def clear(self):
        if self.cursor and not getattr(self.cursor, 'closed', True):
            try:
                self.cursor.commit()
            except Exception:
                _logger.exception('odoo_initializer registry commit failed')
        self.reg = None
        self.env = None
        self.cursor = None


registry = Registry()
