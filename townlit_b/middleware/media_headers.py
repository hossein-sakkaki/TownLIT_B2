from django.http import FileResponse

class AddMediaCORSHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if isinstance(response, FileResponse):
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Headers'] = 'Range'
            response['Access-Control-Expose-Headers'] = 'Content-Range'
            response['Accept-Ranges'] = 'bytes'
        return response
