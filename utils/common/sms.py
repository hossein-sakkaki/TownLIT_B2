# # utils/sms.py

# import logging
# import boto3
# from botocore.exceptions import BotoCoreError, ClientError
# from django.conf import settings

# logger = logging.getLogger("townlit.sms")


# def mask_phone(phone: str) -> str:
#     if not phone:
#         return ""
#     if len(phone) <= 6:
#         return "***"
#     return f"{phone[:3]}***{phone[-4:]}"


# def send_sms(phone_number, message):
#     logger.info(
#         "SMS_SEND_ATTEMPT phone=%s region=%s message_len=%s",
#         mask_phone(phone_number),
#         settings.AWS_SNS_REGION,
#         len(message or ""),
#     )

#     try:
#         sns_client = boto3.client(
#             "sns",
#             region_name=settings.AWS_SNS_REGION,
#             aws_access_key_id=settings.AWS_SNS_ACCESS_KEY_ID,
#             aws_secret_access_key=settings.AWS_SNS_SECRET_ACCESS_KEY,
#         )

#         response = sns_client.publish(
#             PhoneNumber=phone_number,
#             Message=message,
#             MessageAttributes={
#                 "AWS.SNS.SMS.SMSType": {
#                     "DataType": "String",
#                     "StringValue": "Transactional",
#                 },
#                 # اگر SenderID داری، فقط برای کشورهایی که پشتیبانی می‌کنند.
#                 # برای Canada/US معمولاً SenderID جواب نمی‌دهد.
#                 # "AWS.SNS.SMS.SenderID": {
#                 #     "DataType": "String",
#                 #     "StringValue": "TownLIT",
#                 # },
#             },
#         )

#         message_id = response.get("MessageId")
#         request_id = response.get("ResponseMetadata", {}).get("RequestId")

#         logger.info(
#             "SMS_SEND_ACCEPTED phone=%s message_id=%s aws_request_id=%s http_status=%s",
#             mask_phone(phone_number),
#             message_id,
#             request_id,
#             response.get("ResponseMetadata", {}).get("HTTPStatusCode"),
#         )

#         return {
#             "success": True,
#             "message_id": message_id,
#             "aws_request_id": request_id,
#         }

#     except ClientError as e:
#         error = e.response.get("Error", {})
#         logger.exception(
#             "SMS_SEND_CLIENT_ERROR phone=%s code=%s message=%s",
#             mask_phone(phone_number),
#             error.get("Code"),
#             error.get("Message"),
#         )
#         return {
#             "success": False,
#             "error": str(e),
#             "aws_error_code": error.get("Code"),
#             "aws_error_message": error.get("Message"),
#         }

#     except BotoCoreError as e:
#         logger.exception(
#             "SMS_SEND_BOTOCORE_ERROR phone=%s error=%s",
#             mask_phone(phone_number),
#             str(e),
#         )
#         return {"success": False, "error": str(e)}

#     except Exception as e:
#         logger.exception(
#             "SMS_SEND_UNKNOWN_ERROR phone=%s error=%s",
#             mask_phone(phone_number),
#             str(e),
#         )
#         return {"success": False, "error": str(e)}