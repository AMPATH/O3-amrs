# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Sruthi Pavithran (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
import json
import logging
from datetime import datetime

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class RestApi(http.Controller):
    """This is a controller which is used to generate responses based on the
    api requests"""

    def auth_api_key(self, api_key):
        """This function is used to authenticate the api-key when sending a
        request"""
        user_id = request.env['res.users'].sudo().search([('api_key', '=', api_key)])
        if api_key is not None and user_id:
             response = True
        elif not user_id:
            response = ('<html><body><h2>Invalid <i>API Key</i> '
                        '!</h2></body></html>')
        else:
            response = ("<html><body><h2>No <i>API Key</i> Provided "
                        "!</h2></body></html>")
        return response

    def generate_response(self, method, model, rec_id):
        """This function is used to generate the response based on the type
        of request and the parameters given"""
        option = request.env['connection.api'].search(
            [('model_id', '=', model)], limit=1)
        model_name = option.model_id.model
        if method != 'DELETE':
            data = json.loads(request.httprequest.data)
        else:
            data = {}
        fields = []
        if data:
            for field in data['fields']:
                fields.append(field)
        if not fields and method != 'DELETE':
            return ("<html><body><h2>No fields selected for the model"
                    "</h2></body></html>")
        if not option:
            return ("<html><body><h2>No Record Created for the model"
                    "</h2></body></html>")
        try:
            if method == 'GET':
                fields = []
                for field in data['fields']:
                    fields.append(field)
                if not option.is_get:
                    return ("<html><body><h2>Method Not Allowed"
                            "</h2></body></html>")
                else:
                    datas = []
                    if rec_id != 0:
                        partner_records = request.env[
                            str(model_name)
                        ].search_read(
                            domain=[('id', '=', rec_id)],
                            fields=fields
                        )

                        # Manually convert datetime fields to string format
                        for record in partner_records:
                            for key, value in record.items():
                                if isinstance(value, datetime):
                                    record[key] = value.isoformat()
                        data = json.dumps({
                            'records': partner_records
                        })
                        datas.append(data)
                        return request.make_response(data=datas)
                    else:
                        partner_records = request.env[
                            str(model_name)
                        ].search_read(
                            domain=[],
                            fields=fields
                        )

                        # Manually convert datetime fields to string format
                        for record in partner_records:
                            for key, value in record.items():
                                if isinstance(value, datetime):
                                    record[key] = value.isoformat()

                        data = json.dumps({
                            'records': partner_records
                        })
                        datas.append(data)
                        return request.make_response(data=datas)
        except:
            return ("<html><body><h2>Invalid JSON Data"
                    "</h2></body></html>")
        if method == 'POST':
            if not option.is_post:
                return ("<html><body><h2>Method Not Allowed"
                        "</h2></body></html>")
            else:
                try:
                    data = json.loads(request.httprequest.data)
                    datas = []
                    new_resource = request.env[str(model_name)].create(
                        data['values'])
                    partner_records = request.env[
                        str(model_name)].search_read(
                        domain=[('id', '=', new_resource.id)],
                        fields=fields
                    )
                    new_data = json.dumps({'New resource': partner_records, })
                    datas.append(new_data)
                    return request.make_response(data=datas)
                except:
                    return ("<html><body><h2>Invalid JSON Data"
                            "</h2></body></html>")
        if method == 'PUT':
            if not option.is_put:
                return ("<html><body><h2>Method Not Allowed"
                        "</h2></body></html>")
            else:
                if rec_id == 0:
                    return ("<html><body><h2>No ID Provided"
                            "</h2></body></html>")
                else:
                    resource = request.env[str(model_name)].browse(
                        int(rec_id))
                    if not resource.exists():
                        return ("<html><body><h2>Resource not found"
                                "</h2></body></html>")
                    else:
                        try:
                            datas = []
                            data = json.loads(request.httprequest.data)
                            resource.write(data['values'])
                            partner_records = request.env[
                                str(model_name)].search_read(
                                domain=[('id', '=', resource.id)],
                                fields=fields
                            )
                            new_data = json.dumps(
                                {'Updated resource': partner_records,
                                 })
                            datas.append(new_data)
                            return request.make_response(data=datas)

                        except:
                            return ("<html><body><h2>Invalid JSON Data "
                                    "!</h2></body></html>")
        if method == 'DELETE':
            if not option.is_delete:
                return ("<html><body><h2>Method Not Allowed"
                        "</h2></body></html>")
            else:
                if rec_id == 0:
                    return ("<html><body><h2>No ID Provided"
                            "</h2></body></html>")
                else:
                    resource = request.env[str(model_name)].browse(
                        int(rec_id))
                    if not resource.exists():
                        return ("<html><body><h2>Resource not found"
                                "</h2></body></html>")
                    else:

                        records = request.env[
                            str(model_name)].search_read(
                            domain=[('id', '=', resource.id)],
                            fields=['id', 'display_name']
                        )
                        remove = json.dumps(
                            {"Resource deleted": records,
                             })
                        resource.unlink()
                        return request.make_response(data=remove)

    @http.route(['/send_request'], type='http',
                auth='none',
                methods=['GET', 'POST', 'PUT', 'DELETE'], csrf=False)
    def fetch_data(self, **kw):
        """This controller will be called when sending a request to the
        specified url, and it will authenticate the api-key and then will
        generate the result"""
        http_method = request.httprequest.method
        api_key = request.httprequest.headers.get('api-key')
        auth_api = self.auth_api_key(api_key)
        model = kw.get('model')
        username = request.httprequest.headers.get('login')
        password = request.httprequest.headers.get('password')
        request.session.authenticate(request.session.db, username,
                                     password)
        model_id = request.env['ir.model'].search(
            [('model', '=', model)])
        if not model_id:
            return ("<html><body><h3>Invalid model, check spelling or maybe "
                    "the related "
                    "module is not installed"
                    "</h3></body></html>")

        if auth_api == True:
            if not kw.get('Id'):
                rec_id = 0
            else:
                rec_id = int(kw.get('Id'))
            result = self.generate_response(http_method, model_id.id, rec_id)
            return result
        else:
            return auth_api

    def _serialize_record(self, record):
        """Convert datetime values to ISO strings in a record dict."""
        for key, value in record.items():
            if isinstance(value, datetime):
                record[key] = value.isoformat()
        return record

    @http.route(['/get_sale_order'], type='http', auth='none',
                methods=['GET'], csrf=False)
    def get_sale_order(self, **kw):
        """Fetch a sale.order with its order lines and down payments expanded.

        Query params:
          Id (required) - sale.order id

        Request body (JSON, optional):
          {
            "fields": ["id", "name", ...],       -- sale.order fields to return
            "line_fields": ["id", "product_id", ...]  -- sale.order.line fields
          }

        If omitted, sensible defaults are used for both field lists.
        """
        api_key = request.httprequest.headers.get('api-key')
        auth_result = self.auth_api_key(api_key)
        if auth_result is not True:
            return auth_result

        username = request.httprequest.headers.get('login')
        password = request.httprequest.headers.get('password')
        request.session.authenticate(request.session.db, username, password)

        rec_id = kw.get('Id')
        if not rec_id:
            return ("<html><body><h2>Id parameter is required"
                    "</h2></body></html>")
        try:
            rec_id = int(rec_id)
        except (ValueError, TypeError):
            return ("<html><body><h2>Id must be an integer"
                    "</h2></body></html>")

        raw_body = request.httprequest.data
        body = json.loads(raw_body) if raw_body else {}

        order_fields = body.get('fields') or [
            'id', 'name', 'state', 'date_order',
            'partner_id', 'company_id', 'user_id', 'currency_id',
            'amount_untaxed', 'amount_tax', 'amount_total',
            'invoice_status', 'commitment_date', 'note',
            'order_line',
        ]

        line_fields = body.get('line_fields') or [
            'id', 'product_id', 'name', 'product_uom_qty', 'product_uom',
            'price_unit', 'discount', 'tax_id',
            'price_subtotal', 'price_total',
            'qty_delivered', 'qty_invoiced',
            'is_downpayment',
        ]

        # Fetch the sale order
        orders = request.env['sale.order'].search_read(
            domain=[('id', '=', rec_id)],
            fields=order_fields,
        )
        if not orders:
            return ("<html><body><h2>Sale order not found"
                    "</h2></body></html>")

        order = self._serialize_record(orders[0])
        line_ids = order.get('order_line', [])

        # Expand order lines
        order_lines = []
        down_payments = []
        if line_ids:
            lines = request.env['sale.order.line'].search_read(
                domain=[('id', 'in', line_ids)],
                fields=line_fields,
            )
            for line in lines:
                line = self._serialize_record(line)
                if line.get('is_downpayment'):
                    down_payments.append(line)
                else:
                    order_lines.append(line)

        order['order_line'] = order_lines
        order['down_payments'] = down_payments

        return request.make_response(
            data=json.dumps({'records': [order]}),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route(['/odoo_connect'], type="http", auth="none", csrf=False,
                methods=['GET'])
    def odoo_connect(self, **kw):
        """This is the controller which initializes the api transaction by
        generating the api-key for specific user and database"""

        username = request.httprequest.headers.get('login')
        password = request.httprequest.headers.get('password')
        db = request.httprequest.headers.get('db')
        try:
            request.session.update(http.get_default_session(), db=db)
            auth = request.session.authenticate(request.session.db, username,
                                                password)
            user = request.env['res.users'].browse(auth)
            api_key = request.env.user.generate_api(username)
            datas = json.dumps({"Status": "auth successful",
                                "User": user.name,
                                "api-key": api_key})
            return request.make_response(data=datas)
        except:
            return ("<html><body><h2>wrong login credentials"
                    "</h2></body></html>")
