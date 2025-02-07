from odoo import models, fields, _
from odoo.exceptions import UserError
from datetime import datetime
import xml.etree.ElementTree as ET
import base64
import re


class ResInvestor(models.Model):
    _inherit = 'res.investor'

    # Accurate Settings
    accurate_branch_code = fields.Char(string='Accurate Branch Code',
                                       help='Branch code for Accurate integration')
    accurate_exim_id = fields.Char(string='Accurate Exim ID',
                                   help='Export/Import ID for Accurate')
    accurate_dp_account_ref = fields.Char(string='DP Account Reference',
                                          help='Default Down Payment account reference', default='12301')
    accurate_dept_id = fields.Char(string='Department ID',
                                   help='Default department ID', default='1000')
    accurate_default_term = fields.Char(string='Default Payment Term',
                                        help='Default payment term', default='C.O.D')


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_export_accurate(self):
        """Export single PO to Accurate XML format."""
        self.ensure_one()
        self._validate_accurate_export()

        try:
            # Inisialisasi XML content
            xml_parts = []
            xml_parts.append('<?xml version="1.0"?>')
            xml_parts.append(
                f'<NMEXML EximID="{self.investor_id.accurate_exim_id or "124"}" BranchCode="{self.investor_id.accurate_branch_code}" ACCOUNTANTCOPYID="">')
            xml_parts.append('<TRANSACTIONS OnError="CONTINUE">')

            # Header PO
            xml_parts.append('<PO operation="Add" REQUESTID="1">')
            xml_parts.append(f'<POID>{self.id}</POID>')
            xml_parts.append(f'<TRANSACTIONID>{7000 + self.id}</TRANSACTIONID>')

            # Item Lines
            for idx, line in enumerate(self.order_line):
                xml_parts.append('<ITEMLINE operation="Add">')
                xml_parts.append(f'<KeyID>{idx}</KeyID>')
                xml_parts.append(f'<ITEMNO>{line.product_id.default_code}</ITEMNO>')
                xml_parts.append(f'<QUANTITY>{int(line.product_qty)}</QUANTITY>')
                xml_parts.append('<ITEMUNIT/>')
                xml_parts.append('<UNITRATIO>1</UNITRATIO>')

                # Reserved fields
                for i in range(1, 11):
                    xml_parts.append(f'<ITEMRESERVED{i}/>')

                # Item details
                xml_parts.append(f'<ITEMOVDESC>{line.name or line.product_id.name}</ITEMOVDESC>')
                xml_parts.append(f'<UNITPRICE>{int(line.price_unit)}</UNITPRICE>')
                xml_parts.append('<ITEMDISCPC/>')
                xml_parts.append('<TAXCODES/>')
                xml_parts.append(f'<DEPTID>{self.investor_id.accurate_dept_id or "1000"}</DEPTID>')
                xml_parts.append('<GROUPSEQ/>')
                xml_parts.append('<REQUISITIONSEQ/>')
                xml_parts.append('</ITEMLINE>')

            # PO Details
            xml_parts.append(f'<PONO>{self.name}</PONO>')
            xml_parts.append(f'<PODATE>{self.date_order.strftime("%Y-%m-%d")}</PODATE>')
            xml_parts.append('<GLYEAR/>')
            xml_parts.append('<GLPERIOD/>')
            xml_parts.append('<TAX1CODE/>')
            xml_parts.append('<TAX2CODE/>')
            xml_parts.append('<TAX1RATE>0</TAX1RATE>')
            xml_parts.append('<TAX2RATE>0</TAX2RATE>')
            xml_parts.append('<TAX1AMOUNT>0</TAX1AMOUNT>')
            xml_parts.append('<TAX2AMOUNT>0</TAX2AMOUNT>')
            xml_parts.append('<RATE>1</RATE>')
            xml_parts.append('<INCLUSIVETAX>0</INCLUSIVETAX>')
            xml_parts.append('<VENDORISTAXABLE>0</VENDORISTAXABLE>')
            xml_parts.append('<CASHDISCOUNT>0</CASHDISCOUNT>')
            xml_parts.append('<CASHDISCPC>0</CASHDISCPC>')

            # Amount
            total_amount = sum(int(line.product_qty * line.price_unit) for line in self.order_line)
            xml_parts.append(f'<POAMOUNT>{total_amount}</POAMOUNT>')
            xml_parts.append('<FREIGHT>0</FREIGHT>')
            
            # Mendapatkan nama payment term
            payment_term_name = self.payment_term_id.name if self.payment_term_id else ''
            xml_parts.append(f'<TERMREF>{payment_term_name}</TERMREF>')
            
            # xml_parts.append('<TERMREF>C.O.D</TERMREF>')
            xml_parts.append('<FOB/>')
            xml_parts.append('<EXPECTED></EXPECTED>')
            
            # Add notes to description
            notes = self.notes.strip() if self.notes else ''
            cleaned_notes = self.clean_html_tags(notes)
            xml_parts.append(f'<DESCRIPTION>{cleaned_notes}</DESCRIPTION>')

            # Shipping Address
            address_lines = self.investor_id.investor_address.split('\n') if self.investor_id.investor_address else []
            for i in range(1, 6):
                value = address_lines[i - 1] if i <= len(address_lines) else ""
                if value:
                    xml_parts.append(f'<SHIPTO{i}>{value}</SHIPTO{i}>')
                else:
                    xml_parts.append(f'<SHIPTO{i}/>')

            # Footer
            xml_parts.append('<PROCEED/>')
            xml_parts.append('<CLOSED>0</CLOSED>')
            xml_parts.append('<DP/>')
            xml_parts.append(f'<DPACCOUNTREF>{self.investor_id.accurate_dp_account_ref or "110402"}</DPACCOUNTREF>')
            xml_parts.append('<DPUSED/>')
            xml_parts.append(f'<VENDORREF>{self.partner_id.accurate_vendor_code}</VENDORREF>')
            xml_parts.append('</PO>')

            xml_parts.append('</TRANSACTIONS>')
            xml_parts.append('</NMEXML>')

            # Generate XML file
            xml_str = ''.join(xml_parts).replace(' ><', '><').encode('utf-8')
            filename = f'accurate_po_{self.name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xml'

            # Create attachment
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(xml_str),
                'mimetype': 'application/xml',
            })

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }

        except Exception as e:
            raise UserError(f"Error saat generate file: {str(e)}")

    def action_export_accurate_multiple(self):
        """Export multiple PO to Accurate XML format."""
        # Validasi awal
        if not self:
            raise UserError("Tidak ada PO yang dipilih!")

        # Grouping PO berdasarkan investor
        pos_by_investor = {}
        for po in self:
            if not po.investor_id:
                continue
            if po.investor_id not in pos_by_investor:
                pos_by_investor[po.investor_id] = []
            pos_by_investor[po.investor_id].append(po)

        if not pos_by_investor:
            raise UserError("Tidak ada PO dengan investor yang bisa diexport!")

        attachments = []
        error_messages = []

        # Generate XML untuk setiap investor
        for investor, purchase_orders in pos_by_investor.items():
            try:
                # Inisialisasi XML content
                xml_parts = []
                xml_parts.append('<?xml version="1.0"?>')
                xml_parts.append(
                    f'<NMEXML EximID="{investor.accurate_exim_id or "124"}" BranchCode="{investor.accurate_branch_code}" ACCOUNTANTCOPYID="">')
                xml_parts.append('<TRANSACTIONS OnError="CONTINUE">')

                # Generate PO content
                for order in purchase_orders:
                    try:
                        order._validate_accurate_export()

                        # Header PO
                        xml_parts.append('<PO operation="Add" REQUESTID="1">')
                        xml_parts.append(f'<POID>{order.id}</POID>')
                        xml_parts.append(f'<TRANSACTIONID>{7000 + order.id}</TRANSACTIONID>')

                        # Item Lines
                        for idx, line in enumerate(order.order_line):
                            xml_parts.append('<ITEMLINE operation="Add">')
                            xml_parts.append(f'<KeyID>{idx}</KeyID>')
                            xml_parts.append(f'<ITEMNO>{line.product_id.default_code}</ITEMNO>')
                            xml_parts.append(f'<QUANTITY>{int(line.product_qty)}</QUANTITY>')
                            xml_parts.append('<ITEMUNIT/>')
                            xml_parts.append('<UNITRATIO>1</UNITRATIO>')

                            # Reserved fields
                            for i in range(1, 11):
                                xml_parts.append(f'<ITEMRESERVED{i}/>')

                            # Item details
                            xml_parts.append(f'<ITEMOVDESC>{line.name or line.product_id.name}</ITEMOVDESC>')
                            xml_parts.append(f'<UNITPRICE>{int(line.price_unit)}</UNITPRICE>')
                            xml_parts.append('<ITEMDISCPC/>')
                            xml_parts.append('<TAXCODES/>')
                            xml_parts.append(f'<DEPTID>{investor.accurate_dept_id or "1000"}</DEPTID>')
                            xml_parts.append('<GROUPSEQ/>')
                            xml_parts.append('<REQUISITIONSEQ/>')
                            xml_parts.append('</ITEMLINE>')

                        # PO Details
                        xml_parts.append(f'<PONO>{order.name}</PONO>')
                        xml_parts.append(f'<PODATE>{order.date_order.strftime("%Y-%m-%d")}</PODATE>')
                        xml_parts.append('<GLYEAR/>')
                        xml_parts.append('<GLPERIOD/>')
                        xml_parts.append('<TAX1CODE/>')
                        xml_parts.append('<TAX2CODE/>')
                        xml_parts.append('<TAX1RATE>0</TAX1RATE>')
                        xml_parts.append('<TAX2RATE>0</TAX2RATE>')
                        xml_parts.append('<TAX1AMOUNT>0</TAX1AMOUNT>')
                        xml_parts.append('<TAX2AMOUNT>0</TAX2AMOUNT>')
                        xml_parts.append('<RATE>1</RATE>')
                        xml_parts.append('<INCLUSIVETAX>0</INCLUSIVETAX>')
                        xml_parts.append('<VENDORISTAXABLE>0</VENDORISTAXABLE>')
                        xml_parts.append('<CASHDISCOUNT>0</CASHDISCOUNT>')
                        xml_parts.append('<CASHDISCPC>0</CASHDISCPC>')

                        # Amount
                        total_amount = sum(int(line.product_qty * line.price_unit) for line in order.order_line)
                        xml_parts.append(f'<POAMOUNT>{total_amount}</POAMOUNT>')
                        xml_parts.append('<FREIGHT>0</FREIGHT>')
                        
                        # xml_parts.append('<TERMREF>C.O.D</TERMREF>')
                        payment_term_name = order.payment_term_id.name if order.payment_term_id else ''
                        xml_parts.append(f'<TERMREF>{payment_term_name}</TERMREF>')


                        xml_parts.append('<FOB/>')
                        xml_parts.append('<EXPECTED></EXPECTED>')


                        # Add notes to description
                        notes = order.notes.strip() if order.notes else ''
                        cleaned_notes = order.clean_html_tags(notes)
                        xml_parts.append(f'<DESCRIPTION>{cleaned_notes}</DESCRIPTION>')
                        # xml_parts.append('<DESCRIPTION/>')

                        # Shipping Address
                        address_lines = investor.investor_address.split('\n') if investor.investor_address else []
                        for i in range(1, 6):
                            value = address_lines[i - 1] if i <= len(address_lines) else ""
                            if value:
                                xml_parts.append(f'<SHIPTO{i}>{value}</SHIPTO{i}>')
                            else:
                                xml_parts.append(f'<SHIPTO{i}/>')

                        # Footer
                        xml_parts.append('<PROCEED/>')
                        xml_parts.append('<CLOSED>0</CLOSED>')
                        xml_parts.append('<DP/>')
                        xml_parts.append(f'<DPACCOUNTREF>{investor.accurate_dp_account_ref or "110402"}</DPACCOUNTREF>')
                        xml_parts.append('<DPUSED/>')
                        xml_parts.append(f'<VENDORREF>{order.partner_id.accurate_vendor_code}</VENDORREF>')
                        xml_parts.append('</PO>')

                    except Exception as e:
                        error_messages.append(f"Error pada PO {order.name}: {str(e)}")
                        continue

                xml_parts.append('</TRANSACTIONS>')
                xml_parts.append('</NMEXML>')

                # Generate XML file
                xml_str = ''.join(xml_parts).replace(' ><', '><').encode('utf-8')
                filename = f'accurate_po_{investor.name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xml'

                # Create attachment
                attachment = self.env['ir.attachment'].create({
                    'name': filename,
                    'type': 'binary',
                    'datas': base64.b64encode(xml_str),
                    'mimetype': 'application/xml',
                })
                attachments.append(attachment.id)

            except Exception as e:
                error_messages.append(f"Error pada investor {investor.name}: {str(e)}")
                continue

        # Handle errors
        if error_messages:
            raise UserError("\n".join(error_messages))

        if not attachments:
            raise UserError("Tidak ada file yang berhasil di-generate!")

        # Return result
        if len(attachments) == 1:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachments[0]}?download=true',
                'target': 'self',
            }
        else:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/binary/download_multiple_attachments?attachment_ids={",".join(map(str, attachments))}',
                'target': 'self',
            }
        
    def clean_html_tags(self, text):
        """Menghapus tag HTML dari teks."""
        if not text:
            return ''
        
        # Menghapus tag <p> secara spesifik
        # Menghapus semua HTML tags menggunakan regex
        clean_text = re.sub(r'<[^>]+>', '', text)
        
        # Membersihkan whitespace berlebih
        clean_text = ' '.join(clean_text.split())
        
        # Menghapus karakter khusus HTML jika ada
        clean_text = clean_text.replace('&nbsp;', ' ').replace('&amp;', '&')
        
        return clean_text

    def _validate_accurate_export(self):
        """
        Validasi semua data yang diperlukan untuk export ke Accurate
        Raises: UserError dengan pesan spesifik jika ada yang tidak valid
        """
        self.ensure_one()
        errors = []

        # 1. Validasi Investor Settings
        if not self.investor_id:
            errors.append("- PO ini belum memiliki investor. Silakan pilih investor terlebih dahulu.")
        else:
            if not self.investor_id.accurate_branch_code:
                errors.append(f"- Branch Code Accurate untuk investor {self.investor_id.name} belum diisi")
            if not self.investor_id.accurate_exim_id:
                errors.append(f"- Exim ID Accurate untuk investor {self.investor_id.name} belum diisi")
            if not self.investor_id.accurate_dp_account_ref:
                errors.append(f"- Kode akun DP Accurate untuk investor {self.investor_id.name} belum diisi")
            if not self.investor_id.accurate_dept_id:
                errors.append(f"- Kode departemen Accurate untuk investor {self.investor_id.name} belum diisi")

            # 2. Validasi Vendor
        if not self.partner_id:
            errors.append("- Supplier belum dipilih")
        else:
            if not self.partner_id.accurate_vendor_code:
                errors.append(f"- Supplier {self.partner_id.name} belum memiliki kode vendor Accurate. "
                              "Silakan isi kode vendor sesuai dengan yang ada di Accurate")

        # 3. Validasi Item Lines
        if not self.order_line:
            errors.append("- PO tidak memiliki item lines")

        for line in self.order_line:
            # Validasi Product
            if not line.product_id:
                errors.append("- Ditemukan line item tanpa produk")
            elif not line.product_id.default_code:
                errors.append(f"- Produk {line.product_id.name} belum memiliki kode internal (default_code). "
                              "Kode ini diperlukan untuk mapping dengan kode barang di Accurate")

            # Validasi Quantity
            if line.product_qty <= 0:
                errors.append(f"- Quantity untuk produk {line.product_id.name} harus lebih dari 0")

            # Validasi Harga
            if line.price_unit <= 0:
                errors.append(f"- Harga untuk produk {line.product_id.name} harus lebih dari 0")

        # 4. Validasi Alamat
        if not self.investor_id.investor_address:
            errors.append(f"- Alamat untuk investor {self.investor_id.name} belum diisi")

        # Jika ada error, tampilkan semua pesan error
        if errors:
            error_message = "Ditemukan beberapa masalah yang harus diperbaiki sebelum melakukan export ke Accurate:\n\n"
            error_message += "\n".join(errors)
            error_message += "\n\nSilakan perbaiki masalah di atas dan coba export kembali."
            raise UserError(error_message)

        return True
