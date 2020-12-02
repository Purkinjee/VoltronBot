
window.addEventListener('pywebviewready', function() {
	pywebview.api.init();
	pywebview.api.get_module_list().then(function(response) {
		for (module in response) {
			$('#penus').append(
				$('<div>').text(response[module]['module_name'])
			);
		}
	})
});
