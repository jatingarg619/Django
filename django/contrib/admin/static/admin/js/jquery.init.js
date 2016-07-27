/*global django:true, jQuery:false*/
/* Puts the included jQuery into our own namespace using noConflict and passing
 * it 'true'. This ensures that the included jQuery doesn't pollute the global
 * namespace.
 */
var django = django || {};
django.jQuery = jQuery.noConflict(true);
