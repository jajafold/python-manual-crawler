import socket
from enum import Enum
import requests
import re

token = 'ee5b74e38eaa4a1a80b5e4952a709afb'
# <b><code>a99363873f444188875ffba92eb8e396</code></b>
IP = '178.154.226.49'


class ContentType(Enum):
    Heading = 0,
    Cookies = 1,
    Forms = 2,
    Parameters = 3,
    Files = 4


class RequestMethod(Enum):
    HREF = 0,
    GET = 1,
    POST = 2,


def extract_request_method(method: RequestMethod) -> str:
    if method in [RequestMethod.HREF, RequestMethod.GET]:
        return 'GET'
    elif method == RequestMethod.POST:
        return 'POST'


def find_request_method(response: str) -> RequestMethod:
    if 'Перейдите по' in response:
        return RequestMethod.GET
    elif 'GET' in response:
        return RequestMethod.GET
    elif 'POST' in response:
        return RequestMethod.POST
    elif 'Загрузите' in response:
        return RequestMethod.POST


def parse_address(response: str) -> str:
    if 'href' in response:
        start_href = response.find('<a href=')
        end_href = response.find('</a>') + 5

        address = re.findall(r'[\'"]([^"]*)["\']', response[start_href: end_href])[0]
    else:
        address = response[response.find('<code>') + 6: response.find('</code>')]

    return address


def parse_table(ident: str, response: str) -> dict:
    table_start = response.find(ident)
    if table_start == -1:
        return {}

    table_end = response.find('</table>', table_start)
    table_raw = response[table_start: table_end]
    raw_headings = re.findall(r'<code>\w+.*</code>', table_raw)
    table = {}

    for i in range(0, len(raw_headings) - 1, 2):
        table[raw_headings[i][6: -7]] = raw_headings[i + 1][6: -7]

    return table


def parse_content(response: str):
    contents = dict()
    headings = parse_table('заголовки', response)
    cookies = parse_table('cookie', response)
    cookies['user'] = f'{token}'
    forms = parse_table('формы', response)
    parameters = parse_table('параметры запроса', response)
    files = parse_table('файлы', response)

    if headings:
        contents[ContentType.Heading] = headings
    if cookies:
        contents[ContentType.Cookies] = cookies
    if forms:
        contents[ContentType.Forms] = forms
    if parameters:
        contents[ContentType.Parameters] = parameters
    if files:
        contents[ContentType.Files] = files

    return headings, cookies, forms, parameters, files


def receive_data(sc: socket.socket) -> str:
    received_data = ''
    while True:
        try:
            chunk = sc.recv(1024)
        except socket.timeout as e:
            break

        # print(f'CHUNK: {chunk}')

        if not chunk:
            break
        received_data += chunk.decode()

    return received_data


def step_1(sc: socket.socket) -> str:
    request = (
        'GET / HTTP/1.0\r\n'
        'Connection: Keep-Alive\r\n'
        f'cookie: user={token}\r\n'
        '\r\n'
    )
    sc.sendall(request.encode())
    return receive_data(sc)


def step_2(sc: socket.socket, previous_response: str):
    # print(previous_response)

    method_info = find_request_method(previous_response)
    print(f'METHOD: {method_info}')

    address = parse_address(previous_response, method_info)
    print(f'ADDRESS: {address}')

    content = parse_content(previous_response)
    print(f'CONTENT: {content}')

    headings = ''
    if ContentType.Heading in content:
        for key, value in content[ContentType.Heading].items():
            headings += f'{key}: {value}\r\n'

    cookie_pairs = [f'user={token}']
    if ContentType.Cookies in content:
        for key, value in content[ContentType.Cookies].items():
            cookie_pairs.append(f'{key}={value}')
    cookies = 'cookie: ' + '; '.join(cookie_pairs) + '\r\n'

    params = ''
    if ContentType.Parameters in content:
        params = '/?' + '&'.join([f'{key}={value}' for key, value in content[ContentType.Parameters].items()])

    forms = None
    if ContentType.Forms in content:
        forms = '&'.join([f'{key}={value}' for key, value in content[ContentType.Forms].items()])

    forms_body = None
    if forms:
        forms_body = (
            'Content-Type: application/x-www-form-urlencoded\r\n'
            f'Content-Length: {len(forms)}\r\n'
        )

    request = (
            f'{extract_request_method(method_info)} {address}{params} HTTP/1.0\r\n'
            + headings
            + cookies
    )

    if forms:
        request += forms_body
        request += '\r\n'
        request += forms
    else:
        request += '\r\n'

    print('=============REQUEST================')
    print(request)
    print('====================================')

    sc.sendall(request.encode())

    return receive_data(sc)


def pretty_print_POST(req):
    """
    At this point it is completely built and ready
    to be fired; it is "prepared".

    However pay attention at the formatting used in
    this function because it is programmed to be pretty
    printed and may differ from the actual request.
    """
    print('{}\n{}\r\n{}\r\n\r\n{}'.format(
        '-----------START-----------',
        req.method + ' ' + req.url,
        '\r\n'.join('{}: {}'.format(k, v) for k, v in req.headers.items()),
        req.body.decode('utf-8'),
    ))


if __name__ == '__main__':

    response = requests.get(f'http://{IP}', cookies={
        'user': f'{token}'
    })

    while True:
        if 'Секретный ключ' in response.text:
            # print(response.text)
            break

        address = parse_address(response.text)
        headers, cookies, forms, parameters, files = parse_content(response.text)
        if find_request_method(response.text) == RequestMethod.GET:
            response = requests.get(f'http://{IP}{address}',
                                    headers=headers, cookies=cookies, data=forms, params=parameters)
        else:
            if files:
                pretty_print_POST(requests.request('POST', url=f'http://{IP}{address}',
                                                   headers=headers, cookies=cookies, data=forms, params=parameters, files=files).request)
            response = requests.post(f'http://{IP}{address}',
                                     headers=headers, cookies=cookies, data=forms, params=parameters, files=files)

    # with socket.socket() as sc:
    #     sc.connect((IP, 80))
    #     sc.settimeout(2)
    #     response_1 = step_1(sc)
    #     print(response_1)
    #
    #     response_2 = step_2(sc, response_1)
    #     print('2222222222222222222:', response_2)
    #     requests.get()
    #
    #     response_3 = step_2(sc, response_2)
    #     print('3333333333333333333:', response_3)
