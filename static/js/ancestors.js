var pendingRequest = false;

$('body').on('click', function (e) {
    $('.btn-small').each(function () {
        //the 'is' for buttons that trigger popups
        //the 'has' for icons within a button that triggers a popup
        if (!$(this).is(e.target) && $(this).has(e.target).length === 0 && $('.popover').has(e.target).length === 0) {
            $(this).popover('hide');
        }
    });
});

$(document).ready(function(){
    $(document).bind('app.sync',function(){
	getAncestors(person.api_id,true);
    });

    getAncestors(person.api_id,false);
});

function getAncestors(personID,sync) {
    if (pendingRequest)
	return
    var url = '/ancestors/list/'+personID;
    if(sync) {
        url += '?sync';
    }
    pendingRequest = true;
    $("#area").hide();
    $("#loader").show();
    $.ajax({
	url: url,
	success: function(data) {
	    $('#area').html(data);
	    $("#loader").hide();
	    $("#area").show();
	    pendingRequest = false;
	}
    }).error(ajaxErrorHandler);
}
