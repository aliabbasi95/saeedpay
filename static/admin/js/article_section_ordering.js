(function($) {
    'use strict';
    
    function updateSectionOrdering() {
        // Find all order fields in the article section inline
        var orderFields = $('.field-order input[type="number"]');
        var maxOrder = 0;
        
        // Find the highest existing order value
        orderFields.each(function() {
            var value = parseInt($(this).val()) || 0;
            if (value > maxOrder) {
                maxOrder = value;
            }
        });
        
        // Set order for empty fields
        orderFields.each(function() {
            var $field = $(this);
            var currentValue = parseInt($field.val()) || 0;
            
            // If field is empty or 0, assign next order
            if (currentValue === 0) {
                maxOrder++;
                $field.val(maxOrder);
            }
        });
    }
    
    function initializeSectionOrdering() {
        // Update ordering when page loads
        updateSectionOrdering();
        
        // Watch for new inline forms being added
        $(document).on('formset:added', function(event, $row) {
            // Check if this is an article section inline
            if ($row.closest('.inline-group').find('h2').text().includes('بخش مقاله')) {
                setTimeout(function() {
                    updateSectionOrdering();
                }, 100);
            }
        });
        
        // Also handle the "Add another" button click
        $(document).on('click', '.add-row a', function() {
            var $inline = $(this).closest('.inline-group');
            if ($inline.find('h2').text().includes('بخش مقاله')) {
                setTimeout(function() {
                    updateSectionOrdering();
                }, 200);
            }
        });
    }
    
    // Initialize when DOM is ready
    $(document).ready(function() {
        initializeSectionOrdering();
    });
    
})(django.jQuery);
