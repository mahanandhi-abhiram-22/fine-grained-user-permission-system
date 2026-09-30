from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class AccountAuthTests(APITestCase):
    def test_login_returns_access_and_refresh_tokens(self):
        User.objects.create_user(email='admin@example.com', password='StrongPass123!')

        response = self.client.post(
            reverse('token_obtain_pair'),
            {'email': 'admin@example.com', 'password': 'StrongPass123!'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['email'], 'admin@example.com')

    def test_login_requires_valid_credentials(self):
        User.objects.create_user(email='admin@example.com', password='StrongPass123!')

        response = self.client.post(
            reverse('token_obtain_pair'),
            {'email': 'admin@example.com', 'password': 'wrong-pass'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ApiDocumentationAccessTests(APITestCase):
    """The assignment requires authentication on every endpoint except login.

    That includes the generated OpenAPI schema and the Swagger UI, so an
    anonymous request must not be able to read the API map.
    """

    documentation_routes = ('schema', 'swagger-ui')

    def test_documentation_routes_require_authentication(self):
        for route in self.documentation_routes:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))

                self.assertIn(
                    response.status_code,
                    (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
                )

    def test_authenticated_users_can_reach_the_documentation_routes(self):
        User.objects.create_user(email='reader@example.com', password='StrongPass123!')
        login = self.client.post(
            reverse('token_obtain_pair'),
            {'email': 'reader@example.com', 'password': 'StrongPass123!'},
            format='json',
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        for route in self.documentation_routes:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))

                self.assertEqual(response.status_code, status.HTTP_200_OK)
