
from odoo import models, fields, _
from odoo.exceptions import UserError
from datetime import datetime
import xml.etree.ElementTree as ET
import base64


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_export_accurate(self):
        # Create root XML element
        root = ET.Element('accurate')

        for order in self:
            # Create purchase order element
            po = ET.SubElement(root, 'purchaseOrder')

            # Header section
            header = ET.SubElement(po, 'header')

            # Basic PO information
            ET.SubElement(header, 'transactionNo').text = order.name
            ET.SubElement(header, 'transactionDate').text = order.date_order.strftime('%Y-%m-%d')
            ET.SubElement(header, 'dueDate').text = order.date_planned.strftime('%Y-%m-%d')
            ET.SubElement(header, 'description').text = order.notes or ''

            # Vendor information
            vendor_code = order.partner_id.ref or f'SUPP-{order.partner_id.id}'
            ET.SubElement(header, 'vendorId').text = vendor_code

            # Warehouse information
            warehouse_code = order.picking_type_id.warehouse_id.code or 'WH-001'
            ET.SubElement(header, 'warehouseId').text = warehouse_code

            # Currency information
            ET.SubElement(header, 'currencyCode').text = order.currency_id.name
            ET.SubElement(header, 'exchangeRate').text = str(order.currency_rate or 1.0)

            # Payment terms
            payment_days = order.payment_term_id.line_ids[0].days if order.payment_term_id else 0
            ET.SubElement(header, 'paymentTerms').text = str(payment_days)

            # Additional settings
            ET.SubElement(header, 'includeExpense').text = 'false'
            ET.SubElement(header, 'status').text = 'APPROVED'

            # Details section
            details = ET.SubElement(po, 'details')

            # Add order lines
            for line in order.order_line:
                detail = ET.SubElement(details, 'purchaseOrderDetail')

                # Item information
                item_code = line.product_id.default_code or f'ITEM-{line.product_id.id}'
                ET.SubElement(detail, 'itemId').text = item_code
                ET.SubElement(detail, 'quantity').text = str(line.product_qty)
                ET.SubElement(detail, 'unitPrice').text = str(line.price_unit)
                ET.SubElement(detail, 'discountPercent').text = str(line.discount if hasattr(line, 'discount') else 0)

                # Department and project (if available)
                if hasattr(line, 'department_id'):
                    ET.SubElement(detail, 'departmentId').text = line.department_id.code or ''
                if hasattr(line, 'project_id'):
                    ET.SubElement(detail, 'projectId').text = line.project_id.code or ''

                # Tax information
                has_tax = bool(line.taxes_id)
                ET.SubElement(detail, 'taxable').text = str(has_tax).lower()
                if has_tax:
                    tax_code = line.taxes_id[0].name if line.taxes_id else ''
                    ET.SubElement(detail, 'taxId').text = tax_code

        # Convert XML to string
        xml_str = ET.tostring(root, encoding='utf-8', method='xml')

        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'accurate_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xml',
            'type': 'binary',
            'datas': base64.b64encode(xml_str),
            'mimetype': 'application/xml',
        })

        # Return the attachment for download
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }