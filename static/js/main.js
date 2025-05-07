/**
 * KodoAP Invoice Processing - Main JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Feather icons
    if (typeof feather !== 'undefined') {
        feather.replace();
    }
    
    // Setup tooltips if Bootstrap is available
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // Setup date formatting helpers
    setupDateFormatting();
    
    // Setup invoice line item calculations
    setupInvoiceCalculations();
    
    // Setup print functionality
    setupPrintHandling();
});

/**
 * Format dates consistently across the application
 */
function setupDateFormatting() {
    // Format a date in yyyy-mm-dd format
    window.formatDate = function(date) {
        if (!date) return '';
        
        if (typeof date === 'string') {
            date = new Date(date);
        }
        
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        
        return `${year}-${month}-${day}`;
    };
    
    // Format a date and time
    window.formatDateTime = function(date) {
        if (!date) return '';
        
        if (typeof date === 'string') {
            date = new Date(date);
        }
        
        return date.toLocaleString();
    };
    
    // Format currency
    window.formatCurrency = function(amount) {
        if (amount === null || amount === undefined) return '';
        
        return '₹' + parseFloat(amount).toFixed(2);
    };
}

/**
 * Setup invoice calculations for line items and totals
 */
function setupInvoiceCalculations() {
    // Calculate line item amount (quantity * rate)
    window.calculateLineAmount = function(qtyInput, rateInput, amountInput) {
        const qty = parseFloat(qtyInput.value) || 0;
        const rate = parseFloat(rateInput.value) || 0;
        const amount = qty * rate;
        
        amountInput.value = amount.toFixed(2);
        return amount;
    };
    
    // Calculate line item tax (amount * tax_percentage / 100)
    window.calculateLineTax = function(amountInput, taxPercentInput, taxAmountInput) {
        const amount = parseFloat(amountInput.value) || 0;
        const taxPercent = parseFloat(taxPercentInput.value) || 0;
        const taxAmount = amount * taxPercent / 100;
        
        taxAmountInput.value = taxAmount.toFixed(2);
        return taxAmount;
    };
    
    // Calculate invoice totals
    window.calculateInvoiceTotals = function(lineItems, subtotalInput, taxTotalInput, discountInput, totalInput) {
        let subtotal = 0;
        let taxTotal = 0;
        
        lineItems.forEach(item => {
            const amountInput = item.querySelector('.item-amount');
            const taxAmountInput = item.querySelector('.item-tax-amt');
            
            subtotal += parseFloat(amountInput.value) || 0;
            taxTotal += parseFloat(taxAmountInput.value) || 0;
        });
        
        const discount = parseFloat(discountInput.value) || 0;
        const total = subtotal - discount + taxTotal;
        
        subtotalInput.value = subtotal.toFixed(2);
        taxTotalInput.value = taxTotal.toFixed(2);
        totalInput.value = total.toFixed(2);
        
        return {
            subtotal: subtotal,
            taxTotal: taxTotal,
            discount: discount,
            total: total
        };
    };
}

/**
 * Setup print handling
 */
function setupPrintHandling() {
    // Check if page was opened for printing
    if (window.location.search.includes('print=true')) {
        // Add small delay to let the page render
        setTimeout(function() {
            window.print();
        }, 500);
    }
    
    // Set up print button handlers
    document.querySelectorAll('[data-print-target]').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('data-print-target');
            const target = document.getElementById(targetId);
            
            if (target) {
                printElement(target);
            }
        });
    });
}

/**
 * Print a specific element
 */
function printElement(element) {
    const originalContents = document.body.innerHTML;
    const printContents = element.innerHTML;
    
    document.body.innerHTML = printContents;
    window.print();
    document.body.innerHTML = originalContents;
    
    // Re-initialize any scripts that were removed
    if (typeof feather !== 'undefined') {
        feather.replace();
    }
}

/**
 * Convert FormData to JSON object
 */
window.formDataToJson = function(formData) {
    const jsonData = {};
    
    for (const [key, value] of formData.entries()) {
        // Handle nested keys like "vendor[name]" or "line_items[0][description]"
        if (key.includes('[')) {
            const matches = key.match(/^([^\[]+)(?:\[([^\]]+)\])+/);
            
            if (matches) {
                const mainKey = matches[1];
                
                // Check if this is a line item
                if (mainKey === 'line_items') {
                    const itemMatches = key.match(/line_items\[(\d+)\]\[(.*?)\]/);
                    
                    if (itemMatches) {
                        const index = parseInt(itemMatches[1]);
                        const field = itemMatches[2];
                        
                        // Initialize array if needed
                        if (!jsonData[mainKey]) {
                            jsonData[mainKey] = [];
                        }
                        
                        // Ensure the array has this index
                        while (jsonData[mainKey].length <= index) {
                            jsonData[mainKey].push({});
                        }
                        
                        // Set value
                        jsonData[mainKey][index][field] = value;
                    }
                }
                // Handle other nested keys like vendor[name]
                else {
                    const nestedKey = key.match(/\[([^\]]+)\]/)[1];
                    
                    if (!jsonData[mainKey]) {
                        jsonData[mainKey] = {};
                    }
                    
                    jsonData[mainKey][nestedKey] = value;
                }
            }
        } else {
            jsonData[key] = value;
        }
    }
    
    return jsonData;
};

/**
 * Show a toast notification
 */
window.showToast = function(message, type = 'info') {
    // Check if we have the toast container
    let toastContainer = document.getElementById('toast-container');
    
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'position-fixed bottom-0 end-0 p-3';
        toastContainer.style.zIndex = '9999';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toastId = 'toast-' + Date.now();
    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `toast bg-${type} text-white` ;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="toast-header bg-${type} text-white">
            <strong class="me-auto">Notification</strong>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    // Show the toast
    if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
        const toastObj = new bootstrap.Toast(toast);
        toastObj.show();
        
        // Remove after it's hidden
        toast.addEventListener('hidden.bs.toast', function() {
            toast.remove();
        });
    } else {
        // Fallback if Bootstrap is not available
        toast.style.display = 'block';
        setTimeout(function() {
            toast.remove();
        }, 5000);
    }
};
