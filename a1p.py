import argparse
import json
import random
import string

import requests


class OneAccount:

    def __init__(self):
        self._auth_url = 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
        self._token_url = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
        self._api_base_url = 'https://graph.microsoft.com/v1.0/'
        self.http = requests.session()
        self.response_error = 'error.message'
        self.config = {
            'client_id': '',
            'client_secret': '',
            'tenant_id': ''
        }
        self._scope = 'Directory.ReadWrite.All'
        self.token = None

    def get_ms_token(self):
        tenant_id = self.config.get('tenant_id')
        url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
        scope = 'https://graph.microsoft.com/.default'
        post_data = {
            'grant_type': 'client_credentials',
            'client_id': self.config.get('client_id'),
            'client_secret': self.config.get('client_secret'),
            'scope': scope
        }
        result = self.fetch(url, data=post_data).json()
        return result['access_token']

    def enabled_user(self, user, pwd):
        post_data = {
            'accountEnabled': True,
            'usageLocation': 'CN',
        }
        return self.api(f'/users/{user}', json=post_data, method='PATCH')

    def create_user(self):
        subscribed = random.choice(self.get_subscribed(is_print=False))
        domain = self.get_default_domain()
        pwd = ''.join(random.choices(string.ascii_letters + string.digits + '!#$%&()*+-/:;<=>?@', k=10))
        user_name = ''.join(random.choices(string.ascii_letters, k=6))
        user_email = f'{user_name}@{domain}'
        post_data = {
            'accountEnabled': True,
            'displayName': user_name,
            'mailNickname': user_name,
            'passwordPolicies': 'DisablePasswordExpiration, DisableStrongPassword',
            'passwordProfile': {
                'password': pwd,
                'forceChangePasswordNextSignIn': False
            },
            'userPrincipalName': user_email,
            'usageLocation': 'CN'
        }
        self.api('/users', json=post_data, method='POST')
        print(f'{user_email}: {pwd} 创建完成.')
        if subscribed and subscribed.get('sku_id'):
            self._assign_license(user_email, subscribed['sku_id'])
            print(f'{user_email}: 分配订阅完成.')

    def _assign_license(self, user_email, sku_id, **kwargs):
        self.http.headers['Authorization'] = "Bearer {}".format(self.token)
        api = f'/users/{user_email}/assignLicense'
        post_data = {
            'addLicenses': [
                {
                    'disabledPlans': [],
                    'skuId': sku_id
                }
            ],
            'removeLicenses': []
        }
        return self.api(api, json=post_data)

    def get_default_domain(self, **kwargs):
        data = self.api('/domains')
        for item in data['value']:
            if item.get('isDefault'):
                return item.get('id')
        return None

    def get_domains(self, **kwargs):
        return self.api('/domains')

    def get_subscribed(self, is_print=True):
        subscribed_list = self.api('/subscribedSkus')
        result = []
        for i in subscribed_list['value']:
            result.append({'status': i['capabilityStatus'], 'sku_id': i['skuId'],
                           'units': f'{i["consumedUnits"]}/{i["prepaidUnits"]["enabled"]}'})
        if is_print:
            return json.dumps(result, indent=4)
        return result

    def enabled_users(self, data=None):
        if not data:
            data = self.api('/users', params={'$select': 'id,accountEnabled,mail,userPrincipalName',
                                              '$filter': 'accountEnabled eq false', '$top': 20})
        for item in data['value']:
            user = item['userPrincipalName']
            pwd = ''.join(random.choices(string.ascii_uppercase + string.digits + string.ascii_lowercase, k=10))
            try:
                self.enabled_user(user, pwd)
                print(f'{user} {pwd} 启用成功')
            except Exception as e:
                print(f'{user} {pwd} 启用失败. {e}')

        if data.get('@odata.nextLink'):
            result = self.api(data['@odata.nextLink'])
            self.enabled_users(result)

    def api(self, api_sub_url, params=None, data=None, method=None, **kwargs):
        self.http.headers['Authorization'] = "Bearer {}".format(self.token)

        if api_sub_url.find('http') == -1:
            url = '{}/{}'.format(self._api_base_url.strip('/'), api_sub_url.strip('/'))
        else:
            url = api_sub_url
        response = self.fetch(url, data=data, method=method, params=params, **kwargs)
        if len(response.content) > 1:
            return response.json()
        return {'status_code': response.status_code}

    def fetch(self, url, data=None, method=None, **kwargs):
        kwargs.setdefault('timeout', 20)
        if (data or kwargs.get('json')) and method is None:
            method = 'POST'

        if method is None:
            method = 'GET'
        response = self.http.request(method, url, data=data, **kwargs)
        if response.ok:
            return response
        raise Exception(response.url, response.status_code, response.json())


def run():
    one = OneAccount()
    parser = argparse.ArgumentParser()
    parser.add_argument('action', nargs='?', default='get_subscribed')
    parsed_args = parser.parse_args()
    params = vars(parsed_args)

    action = params.get('action')
    if hasattr(one, action):
        one.token = one.get_ms_token()
        data = getattr(one, action)()
        if data:
            print(data)
    # print(one.get_subscribed(print=True))


if __name__ == '__main__':
    run()
