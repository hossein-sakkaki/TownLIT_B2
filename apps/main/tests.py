from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import TermsAndPolicy, FAQ, SiteAnnouncement, UserFeedback, UserActionLog

CustomUser = get_user_model()


class AdminSiteTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_superuser(
            email='admin@example.com',
            password='password123',
            mobile_number='1234567890',
            name='Admin',
            family='User',
            username='admin_user'
        )
        self.client.force_login(self.admin_user)

        self.user = CustomUser.objects.create_user(
            email='user@example.com',
            password='password123',
            mobile_number='0987654321',
            name='Test',
            family='User',
            username='test_user'
        )

        self.terms_and_policy = TermsAndPolicy.objects.create(
            policy_type='Privacy Policy',
            title='Privacy Policy Example',
            content='This is a sample privacy policy.',
            is_active=True
        )

        self.faq = FAQ.objects.create(
            question='What is TownLIT?',
            answer='TownLIT is a social and communication network.',
            is_active=True
        )

        self.site_announcement = SiteAnnouncement.objects.create(
            title='New Features',
            content='We have introduced new features in TownLIT.',
            publish_date='2024-10-10',
            is_active=True
        )

        self.user_feedback = UserFeedback.objects.create(
            user=self.user,
            title='Feature Request',
            content='Please add a dark mode feature.'
        )

        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(TermsAndPolicy)

        self.user_action_log = UserActionLog.objects.create(
            user=self.user,
            action_type='view',
            content_type=content_type,
            object_id=self.terms_and_policy.id,
            action_timestamp='2024-10-11T10:00:00Z'
        )

    def test_terms_and_policy_listed(self):
        """
        Test that Terms and Policies are listed on admin page.
        """
        url = reverse('admin:main_termsandpolicy_changelist')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.terms_and_policy.title)

    def test_faq_listed(self):
        """
        Test that FAQs are listed on admin page.
        """
        url = reverse('admin:main_faq_changelist')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.faq.question)

    def test_site_announcement_listed(self):
        """
        Test that Site Announcements are listed on admin page.
        """
        url = reverse('admin:main_siteannouncement_changelist')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.site_announcement.title)

    def test_user_feedback_listed(self):
        """
        Test that User Feedbacks are listed on admin page.
        """
        url = reverse('admin:main_userfeedback_changelist')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user_feedback.title)

    def test_user_action_log_listed(self):
        """
        Test that User Action Logs are listed on admin page.
        """
        url = reverse('admin:main_useractionlog_changelist')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user_action_log.get_action_type_display())