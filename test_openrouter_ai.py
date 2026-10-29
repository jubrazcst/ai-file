"""Offline unit tests; dependencies are stubbed only if unavailable."""
import importlib.util
import json
import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

if importlib.util.find_spec('requests') is None:
    module = types.ModuleType('requests')
    module.RequestException = type('RequestException', (Exception,), {})
    module.post = Mock()
    sys.modules['requests'] = module
if importlib.util.find_spec('websocket') is None:
    module = types.ModuleType('websocket')
    module.WebSocketTimeoutException = type('WebSocketTimeoutException', (Exception,), {})
    sys.modules['websocket'] = module

from openrouter_ai import AIResponder, AIError, gateway_loop, is_trigger, text_parts


def event(mid='10', author='2', mentions=None, reply=None, channel='20'):
    return {'id': mid, 'channel_id': channel, 'guild_id': '30', 'content': '<@1> hello',
            'author': {'id': author}, 'mentions': mentions if mentions is not None else [{'id': '1'}],
            'referenced_message': reply}


def response(status=200, answer='hello', data=None):
    return Mock(status_code=status, headers={}, json=Mock(return_value=data if data is not None else
                {'choices': [{'message': {'content': answer}}]}))


class Tests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'OPENROUTER_API_KEY': 'fake-key',
            'OPENROUTER_MODEL': 'provider/model', 'GUILD_ID': '30', 'AI_COOLDOWN_SECONDS': '1'}, clear=True)
        self.env.start()
        with patch('builtins.print'):
            self.ai = AIResponder('fake-user-token', '1', start_worker=False)

    def tearDown(self): self.env.stop()

    def test_triggers(self):
        self.assertTrue(is_trigger(event(), '1'))
        self.assertTrue(is_trigger(event(mentions=[], reply={'author': {'id': '1'}}), '1'))
        self.assertFalse(is_trigger(event(mentions=[]), '1'))
        self.assertFalse(is_trigger(event(author='1'), '1'))
        e = event(); e['author']['bot'] = True
        self.assertFalse(is_trigger(e, '1'))

    def test_filters(self):
        e=event(); e['guild_id']='other'; self.assertFalse(self.ai.submit(e))
        e=event(); del e['guild_id']; self.assertFalse(self.ai.submit(e))
        self.ai.channels={'21'}; self.assertFalse(self.ai.submit(event()))
        self.assertTrue(self.ai.submit(event(channel='21')))

    def test_duplicate_pending_and_hourly(self):
        self.assertTrue(self.ai.submit(event()))
        self.assertFalse(self.ai.submit(event()))
        self.assertFalse(self.ai.submit(event(mid='11')))
        self.ai.hourly_limit=1
        self.assertFalse(self.ai.submit(event(mid='12', author='3')))

    def test_queue_bound(self):
        for i in range(10): self.assertTrue(self.ai.submit(event(mid=str(100+i),author=str(100+i))))
        self.assertFalse(self.ai.submit(event(mid='999',author='999')))

    def test_missing_key_disables(self):
        os.environ['OPENROUTER_API_KEY']=''
        with patch('builtins.print'): ai=AIResponder('existing', '1', False)
        self.assertFalse(ai.active)
        self.assertFalse(ai.submit(event()))

    def test_provider_payload_and_no_bot_auth(self):
        with patch('openrouter_ai.requests.post', return_value=response()) as post:
            self.assertEqual(self.ai.completion([], 'hi'), 'hello')
        kwargs=post.call_args.kwargs
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer fake-key')
        self.assertEqual(kwargs['json']['model'], 'provider/model')
        self.assertEqual(self.ai.headers['Authorization'], 'fake-user-token')

    def test_invalid_key_no_retry(self):
        with patch('openrouter_ai.requests.post', return_value=response(401)) as post:
            with self.assertRaises(AIError): self.ai.completion([], 'hi')
        self.assertEqual(post.call_count,1)

    def test_retry_limit(self):
        with patch('openrouter_ai.requests.post', side_effect=[response(503),response()]) as post, patch('openrouter_ai.time.sleep'):
            self.assertEqual(self.ai.completion([], 'hi'), 'hello')
        self.assertEqual(post.call_count,2)

    def test_long_retry_after_not_shortened(self):
        r=response(429);r.headers={'Retry-After':'60'}
        with patch('openrouter_ai.requests.post',return_value=r) as post:
            with self.assertRaises(AIError): self.ai.completion([], 'hi')
        self.assertEqual(post.call_count,1)

    def test_malformed_response(self):
        with patch('openrouter_ai.requests.post',return_value=response(data={'choices':[]})):
            with self.assertRaises(AIError):self.ai.completion([], 'hi')

    def test_send_denial_stops_no_bypass(self):
        with patch('openrouter_ai.requests.post',return_value=response(403)) as post, patch('builtins.print'):
            self.assertFalse(self.ai.send(event(),'answer'))
        self.assertTrue(self.ai.stopped)
        self.assertEqual(post.call_count,1)
        self.assertFalse(self.ai.submit(event()))

    def test_no_ping_and_reply(self):
        with patch('openrouter_ai.requests.post',return_value=response()) as post:
            self.assertTrue(self.ai.send(event(),'@everyone hi'))
        payload=post.call_args.kwargs['json']
        self.assertEqual(payload['allowed_mentions'],{'parse':[], 'replied_user':False})
        self.assertEqual(payload['message_reference']['message_id'],'10')
        self.assertTrue(payload['content'].startswith('AI: '))

    def test_memory_reset_and_isolation(self):
        self.ai.submit(event())
        scope=('30','20','2')
        with patch.object(self.ai,'completion',return_value='answer'),patch.object(self.ai,'send',return_value=True):
            self.ai.process(scope,event())
            self.assertEqual(len(self.ai.states[scope]['history']),2)
            self.ai.submit(event(mid='99',author='3'))
            self.assertEqual(self.ai.states[('30','20','3')]['history'],[])
            e=event();e['content']='<@1> !ai reset';self.ai.process(scope,e)
            self.assertEqual(self.ai.states[scope]['history'],[])

    def test_utf16_splitting(self):
        text='😀'*2200+'বাংলা'
        parts=list(text_parts(text));self.assertEqual(''.join(parts),text)
        self.assertTrue(all(len(p.encode('utf-16-le'))//2<=1900 for p in parts))

    def test_gateway_ready_heartbeat_dispatch(self):
        events=[{'op':0,'t':'READY','s':1,'d':{}},{'op':1,'d':None},
                {'op':11,'d':None},{'op':0,'t':'MESSAGE_CREATE','s':2,'d':event()},{'op':7}]
        ws=Mock();ws.recv.side_effect=[json.dumps(e) for e in events]
        responder=Mock();voice={'op':4,'d':{'guild_id':'30','channel_id':'40'}}
        with patch('openrouter_ai.random.random',return_value=1):
            gateway_loop(ws,40000,responder,voice,clock=lambda:0)
        sent=[json.loads(c.args[0]) for c in ws.send.call_args_list]
        self.assertIn(voice,sent);self.assertIn({'op':1,'d':1},sent)
        responder.submit.assert_called_once_with(event())


if __name__=='__main__':unittest.main()
