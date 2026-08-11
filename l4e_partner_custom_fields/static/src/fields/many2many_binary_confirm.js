/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Many2ManyBinaryField, many2ManyBinaryField } from "@web/views/fields/many2many_binary/many2many_binary_field";

export class Many2ManyBinaryConfirmField extends Many2ManyBinaryField {
    setup() {
        super.setup();
        this.dialog = useService("dialog");
    }

    async onFileRemove(deleteId) {
        const record = this.props.record.data[this.props.name].records.find(
            (r) => r.resId === deleteId
        );
        this.dialog.add(ConfirmationDialog, {
            title: _t("Confirm Certificate Removal"),
            body: _t("Are you sure you want to remove this certificate file?"),
            confirmLabel: _t("Ok"),
            cancelLabel: _t("Cancel"),
            confirm: () => {
                if (record) {
                    this.operations.removeRecord(record);
                }
            },
            cancel: () => {},
        });
    }
}

export const many2ManyBinaryConfirmField = {
    ...many2ManyBinaryField,
    component: Many2ManyBinaryConfirmField,
};

registry.category("fields").add("many2many_binary_confirm", many2ManyBinaryConfirmField);
