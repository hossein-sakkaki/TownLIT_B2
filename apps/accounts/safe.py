# from django.shortcuts import get_object_or_404
# from django.contrib.auth import authenticate, login, logout
# from django.utils import timezone
# import datetime

# from rest_framework import status
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated, AllowAny

# from rest_framework_simplejwt.tokens import RefreshToken
# from two_factor.utils import default_device
# from two_factor.views import otp_login
# from django_otp.plugins.otp_totp.models import TOTPDevice
# from django.conf import settings
# from cryptography.fernet import Fernet

# from .serializers import (
#     RegisterUserSerializer, ArrivalUserSerializer, VerifyNewBornSerializer, ForgetPasswordSerializer, ResetPasswordSerializer,
#     )
# import townlit_b.common.utils as utils
# from django.contrib.auth import get_user_model

# CustomUser = get_user_model()


# # Generate key for encryption ---------------------------------------------------
# cipher_suite = Fernet(settings.FERNET_KEY)







# # BORN USER View -----------------------------------------------------------------
# class NewBornUserView(APIView): # Sign in
#     permission_classes = [AllowAny]
    
#     def post(self, request):
#         ser_data = RegisterUserSerializer(data=request.data)
#         if ser_data.is_valid():
#             user = ser_data.create(ser_data.validated_data)
            
#             # Encrypt the active code
#             encrypted_active_code = cipher_suite.encrypt(user.user_active_code.encode())
#             request.session['user_session'] = {
#                 'active_code': encrypted_active_code.decode(),
#                 'email': request.data.get('email'),
#                 'forget_password': False
#             }
#             request.session.save()
#             return Response({"message": "User registered successfully"}, status=status.HTTP_200_OK)
#         return Response(ser_data.errors, status=status.HTTP_400_BAD_REQUEST)

# # VERIFY CODE View -----------------------------------------------------------------
# class VerifyNewBornView(APIView):   # Verify Code
#     permission_classes = [AllowAny]

#     def post(self, request):
#         ser_data = VerifyNewBornSerializer(data=request.data)
#         if ser_data.is_valid():
#             user_session = request.session.get('user_session')
#             if user_session:
#                 encrypted_active_code = user_session.get('active_code')
#                 decrypted_active_code = cipher_suite.decrypt(encrypted_active_code.encode()).decode()
                
#                 if decrypted_active_code == ser_data.validated_data['active_code']:
#                     user = CustomUser.objects.get(email=user_session['email'])
#                     user.is_active = True
#                     user.save()
#                     return Response({"message": "User verified successfully"}, status=status.HTTP_200_OK)
#                 else:
#                     return Response({"error": "Incorrect active code"}, status=status.HTTP_400_BAD_REQUEST)
#             return Response({"error": "Session data not found"}, status=status.HTTP_400_BAD_REQUEST)


# # ARRIVAL USER View -----------------------------------------------------------------
# class ArrivalUserView(APIView): # Login
#     permission_classes = [AllowAny]

#     def post(self, request):
#         ser_data = ArrivalUserSerializer(data=request.data)
#         if ser_data.is_valid():
#             # Authenticate user
#             user = authenticate(username=ser_data.validated_data['email'], password=ser_data.validated_data['password'])
#             if user is not None:
#                 if user.is_active:
#                     # Check if user has a valid TOTP device (for 2FA)
#                     device = default_device(user)
#                     if device is None:  # No 2FA enabled
#                         refresh = RefreshToken.for_user(user)
#                         return Response({
#                             'refresh': str(refresh),
#                             'access': str(refresh.access_token),
#                         }, status=status.HTTP_200_OK)
#                     else:  # 2FA enabled
#                         otp_login(request, user)  # OTP login to start the 2FA process
#                         return Response({"message": "2FA required. Please provide your one-time code."}, status=status.HTTP_202_ACCEPTED)
#                 else:
#                     return Response({"message": "User is not active."}, status=status.HTTP_403_FORBIDDEN)
#             else:
#                 return Response({"message": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)
#         return Response(ser_data.errors, status=status.HTTP_400_BAD_REQUEST)
    

        
# # LOGOUT USER View -----------------------------------------------------------------
# class LogoutUserView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         try:
#             refresh_token = request.data["refresh"]
#             token = RefreshToken(refresh_token)
#             token.blacklist()  # Add token to blacklist
#             return Response({"message": "User has been successfully logged out."}, status=status.HTTP_200_OK)
#         except Exception as e:
#             return Response({"error": "Invalid token or token has already been blacklisted."}, status=status.HTTP_400_BAD_REQUEST)

    
# # FORGET PASSWORD View -----------------------------------------------------------------
# class ForgetPasswordView(APIView):  # Forget Password
#     permission_classes = [AllowAny]

#     def post(self, request):
#         ser_data = ForgetPasswordSerializer(data=request.data)
#         if ser_data.is_valid():
#             user = get_object_or_404(CustomUser, email=ser_data.validated_data['email'])
#             reset_token = cipher_suite.encrypt(user.email.encode()).decode()
#             expiration_time = timezone.now() + datetime.timedelta(minutes=30)
#             user.reset_token = reset_token
#             user.reset_token_expiration = expiration_time
#             user.save()

#             reset_link = f'{utils.MAIN_URL}/reset-password/{reset_token}/'
#             subject = 'Password Reset Link'
#             email_body = f'''
#                 <p>Hello {user.name},</p>
#                 <p>Click the link below to reset your password:</p>
#                 <a href="{reset_link}">{reset_link}</a>
#             '''
#             utils.send_email(subject, email_body, [user.email])
#             return Response({"message": "Password reset link sent"}, status=status.HTTP_200_OK)
#         return Response(ser_data.errors, status=status.HTTP_400_BAD_REQUEST)

    
    
# # RESET PASSWORD View -----------------------------------------------------------------
# class ResetPasswordView(APIView):   # Reset Password
#     permission_classes = [AllowAny]

#     def post(self, request, reset_token, *args, **kwargs):
#         user = get_object_or_404(CustomUser, reset_token=reset_token, reset_token_expiration__gt=timezone.now())
#         ser_data = ResetPasswordSerializer(data=request.data)
#         if ser_data.is_valid():
#             user.set_password(ser_data.validated_data['new_password'])
#             user.reset_token = None
#             user.reset_token_expiration = None
#             user.is_active = True
#             user.save()
#             login(request, user)
#             refresh = RefreshToken.for_user(user)
#             return Response({
#                 'refresh': str(refresh),
#                 'access': str(refresh.access_token),
#             }, status=status.HTTP_200_OK)
#         return Response(ser_data.errors, status=status.HTTP_400_BAD_REQUEST)



# # ENABLE TOW FACTOR View -----------------------------------------------------------------
# # Enable
# class EnableTwoFactorView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         user = request.user
#         # Check if 2FA is already enabled
#         if user.two_factor_enabled:
#             return Response({"message": "Two-factor authentication is already enabled."}, status=status.HTTP_400_BAD_REQUEST)

#         # Create or get TOTP device
#         device, created = TOTPDevice.objects.get_or_create(user=user, confirmed=False)
        
#         # Return the QR code URL for the user to scan
#         return Response({
#             "qr_code_url": device.config_url  # URL that can be used to scan the QR code in the authenticator app
#         }, status=status.HTTP_200_OK)

#     def post(self, request):
#         user = request.user
#         otp_code = request.data.get("otp_code")
        
#         # Get the user's TOTP device
#         device = default_device(user)
#         if device is None:
#             return Response({"error": "No 2FA device found. Please scan the QR code first."}, status=status.HTTP_400_BAD_REQUEST)
        
#         # Verify the OTP code
#         if device.verify_token(otp_code):
#             device.confirmed = True
#             device.save()
#             user.two_factor_enabled = True
#             user.save()
#             return Response({"message": "Two-factor authentication enabled successfully."}, status=status.HTTP_200_OK)
#         else:
#             return Response({"error": "Invalid OTP code."}, status=status.HTTP_400_BAD_REQUEST)

# # Disable  
# class DisableTwoFactorView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         user = request.user        
#         # Check if 2FA is enabled
#         if not user.two_factor_enabled:
#             return Response({"error": "Two-factor authentication is not enabled."}, status=status.HTTP_400_BAD_REQUEST)
#         # Disable 2FA
#         user.two_factor_enabled = False
#         user.save()
#         # Remove the TOTP device
#         TOTPDevice.objects.filter(user=user).delete()
#         return Response({"message": "Two-factor authentication disabled successfully."}, status=status.HTTP_200_OK)












# from django.urls import path
# from . import views

# app_name = 'accounts'
# urlpatterns = [
#     path('born/',views.NewBornUserView.as_view(),name='born'),
#     path('verify/',views.VerifyNewBornView.as_view(),name='verify'),
#     path('arrival/',views.ArrivalUserView.as_view(),name='arrival'),
#     path('logout/',views.LogoutUserView.as_view(), name='logout'),
#     path('forget-password/', views.ForgetPasswordView.as_view(), name='forget-password'),
#     path('reset-password/<str:reset_token>/', views.ResetPasswordView.as_view(), name='reset-password'),
    
#     path('enable-2fa/', views.EnableTwoFactorView.as_view(), name='enable-2fa'),
#     path('disable-2fa/', views.DisableTwoFactorView.as_view(), name='disable-2fa'),
# ]