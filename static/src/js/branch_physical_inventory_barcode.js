/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { onMounted, onWillUnmount } from "@odoo/owl";

function isEditable(element) {
    return Boolean(element?.matches?.('input,textarea,[contenteditable="true"]'));
}

export class BranchPhysicalInventoryBarcodeListController extends ListController {
    setup() {
        super.setup();
        this.barcode = useService("barcode");
        this.notification = useService("notification");
        this.scanBuffer = "";
        this.scanTarget = null;
        this.scanInitialValue = null;
        this.scanTimeout = null;
        this.maxTimeBetweenKeysInMs = 100;
        this.editableBarcodeKeydown = this.onEditableBarcodeKeydown.bind(this);

        useBus(this.barcode.bus, "barcode_scanned", this.onBarcodeScanned.bind(this));
        onMounted(() => {
            document.body.addEventListener("keydown", this.editableBarcodeKeydown, true);
        });
        onWillUnmount(() => {
            document.body.removeEventListener("keydown", this.editableBarcodeKeydown, true);
            clearTimeout(this.scanTimeout);
        });
    }

    resetEditableBarcodeBuffer() {
        this.scanBuffer = "";
        this.scanTarget = null;
        this.scanInitialValue = null;
        clearTimeout(this.scanTimeout);
        this.scanTimeout = null;
    }

    restoreEditableTarget() {
        if (this.scanTarget && "value" in this.scanTarget && this.scanInitialValue !== null) {
            this.scanTarget.value = this.scanInitialValue;
            this.scanTarget.dispatchEvent(new Event("input", { bubbles: true }));
        }
    }

    onEditableBarcodeKeydown(ev) {
        if (!isEditable(ev.target)) {
            return;
        }
        if (!ev.key || ev.metaKey) {
            return;
        }

        const isEndCharacter = ev.key === "Enter" || ev.key === "Tab";
        const isSpecialKey = !["Control", "Alt"].includes(ev.key) && ev.key.length > 1;
        if (isSpecialKey && !isEndCharacter) {
            this.resetEditableBarcodeBuffer();
            return;
        }

        if (!this.scanBuffer) {
            this.scanTarget = ev.target;
            this.scanInitialValue = "value" in ev.target ? ev.target.value : null;
        }

        clearTimeout(this.scanTimeout);
        if (isEndCharacter) {
            const barcode = this.scanBuffer.replace(/Alt|Shift|Control/g, "");
            if (barcode.length >= 3) {
                ev.preventDefault();
                ev.stopPropagation();
                this.restoreEditableTarget();
                this.onBarcodeScanned({ detail: { barcode } });
            }
            this.resetEditableBarcodeBuffer();
            return;
        }

        this.scanBuffer += ev.key;
        this.scanTimeout = setTimeout(
            () => this.resetEditableBarcodeBuffer(),
            this.maxTimeBetweenKeysInMs
        );
    }

    async onBarcodeScanned(ev) {
        const barcode = ev.detail.barcode;
        if (!barcode || this.props.resModel !== "stock.quant") {
            return;
        }
        if (this.editedRecord && !(await this.editedRecord.save())) {
            return;
        }
        try {
            const result = await this.orm.call(
                "stock.quant",
                "action_branch_increment_inventory_by_barcode",
                [barcode, this.model.root.domain],
                { context: this.props.context }
            );
            await this.model.root.load();
            this.notification.add(
                _t("%s counted quantity: %s")
                    .replace("%s", result.product)
                    .replace("%s", result.counted_quantity),
                { title: _t("Barcode scanned"), type: "success" }
            );
        } catch (error) {
            this.notification.add(error.message || _t("Unable to process barcode."), {
                title: _t("Barcode scan failed"),
                type: "danger",
            });
        }
    }
}

export const branchPhysicalInventoryBarcodeListView = {
    ...listView,
    Controller: BranchPhysicalInventoryBarcodeListController,
};

registry.category("views").add(
    "branch_physical_inventory_barcode_list",
    branchPhysicalInventoryBarcodeListView
);
