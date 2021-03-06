import base64
import datetime
import hmac
import json
import random
from hashlib import sha1
from urllib.parse import urlparse
import requests

s = requests.Session()


class JodelAccount:
    post_colors = ['9EC41C', 'FF9908', 'DD5F5F', '8ABDB0', '06A3CB', 'FFBA00']

    api_url = "https://api.go-tellm.com/api%s"
    client_id = '81e8a76e-1e02-4d17-9ba0-8a7020261b26'
    secret = bytearray([ord(c) for c in "OjZvbmHjcGoPhz6OfjIeDRzLXOFjMdJmAIplM7Gq"])
    version = 'android_4.37.2'

    access_token = None
    device_uid = None

    def __init__(self, lat, lng, city, country=None, name=None, update_location=True,
                 access_token=None, device_uid=None, refresh_token=None, distinct_id=None, expiration_date=None, 
                 **kwargs):
        self.lat, self.lng, self.location_dict = lat, lng, self._get_location_dict(lat, lng, city, country, name)

        if access_token and device_uid and refresh_token and distinct_id and expiration_date:
            self.expiration_date = expiration_date
            self.distinct_id = distinct_id
            self.refresh_token = refresh_token
            self.device_uid = device_uid
            self.access_token = access_token
            if update_location:
                r = self.set_location(lat, lng, city, country, name, **kwargs)
                if r[0] != 204:
                    raise Exception("Error updating location: " + str(r))

        else:
            print("Creating new account.")
            r = self.refresh_all_tokens(**kwargs)
            if r[0] != 200:
                raise Exception("Error creating new account: " + str(r))

    def _send_request(self, method, endpoint, params=None, payload=None, **kwargs):
        url = self.api_url % endpoint
        headers = {'User-Agent': 'Jodel/4.4.9 Dalvik/2.1.0 (Linux; U; Android 5.1.1; )',
                   'Accept-Encoding': 'gzip',
                   'Content-Type': 'application/json; charset=UTF-8',
                   'Authorization': 'Bearer ' + self.access_token if self.access_token else None}

        for i in range(3):
            self._sign_request(method, url, headers, params, payload)
            resp = s.request(method=method, url=url, params=params, json=payload, headers=headers, **kwargs)
            if resp.status_code != 502: # Retry on error 502 "Bad Gateway"
                break

        try:
            resp_text = resp.json(encoding="utf-8")
        except:
            resp_text = resp.text

        return resp.status_code, resp_text

    def _sign_request(self, method, url, headers, params={}, payload=None):
        timestamp = datetime.datetime.utcnow().isoformat()[:-7] + "Z"

        req = [method,
               urlparse(url).netloc,
               "443",
               urlparse(url).path,
               self.access_token if self.access_token else "",
               timestamp,
               "%".join(sorted("{}%{}".format(key, value) for key, value in (params if params else {}).items())),
               json.dumps(payload) if payload else ""]

        signature = hmac.new(self.secret, "%".join(req).encode("utf-8"), sha1).hexdigest().upper()

        headers['X-Authorization'] = 'HMAC ' + signature
        headers['X-Client-Type'] = self.version
        headers['X-Timestamp'] = timestamp
        headers['X-Api-Version'] = '0.2'

    @staticmethod
    def _get_location_dict(lat, lng, city, country=None, name=None):
        return {"loc_accuracy": 0.0, 
                "city": city, 
                "loc_coordinates": {"lat": lat, "lng": lng}, 
                "country": country if country else "DE", 
                "name": name if name else city}

    def refresh_all_tokens(self, **kwargs):
        """ Creates a new account with random ID if self.device_uid is not set. Otherwise renews all tokens of the
        account with ID = self.device_uid. """
        if not self.device_uid:
            self.device_uid = ''.join(random.choice('abcdef0123456789') for _ in range(64))

        payload = {"client_id": self.client_id, 
                   "device_uid": self.device_uid,
                   "location": self.location_dict}

        resp = self._send_request("POST", "/v2/users", payload=payload, **kwargs)
        if resp[0] == 200:
            self.access_token = resp[1]['access_token']
            self.expiration_date = resp[1]['expiration_date']
            self.refresh_token = resp[1]['refresh_token']
            self.distinct_id = resp[1]['distinct_id']
        else:
            raise Exception(resp)
        return resp

    def refresh_access_token(self, **kwargs):
        payload = {"client_id": self.client_id, 
                   "distinct_id": self.distinct_id, 
                   "refresh_token": self.refresh_token}

        resp = self._send_request("POST", "/v2/users/refreshToken", payload=payload, **kwargs)
        if resp[0] == 200:
            self.access_token = resp[1]['access_token']
            self.expiration_date = resp[1]['expiration_date']
        return resp

    def verify_account(self):
        r = self.get_user_config()
        if r[0] == 200 and r[1]['verified'] == True:
            print("Account is already verified.")
            return

        while True:
            r = self.get_captcha()
            if r[0] != 200:
                raise Exception(str(r[1]))

            print(r[1]['image_url'])
            answer = input("Open the url above in a browser and enter the images containing a racoon (left to right, starting with 0) separated by spaces: ")
            
            try:
                answer = [int(i) for i in answer.split(' ')]
            except:
                print("Invalid input. Retrying ...")
                continue

            r = self.submit_captcha(r[1]['key'], answer)
            if r[0] == 200 and r[1]['verified'] == True:
                print("Account successfully verified.")
                return
            else:
                print("Verification failed. Retrying ...")

            
    def get_account_data(self):
        return {'expiration_date': self.expiration_date, 'distinct_id': self.distinct_id,
                'refresh_token': self.refresh_token, 'device_uid': self.device_uid, 'access_token': self.access_token}

    def set_location(self, lat, lng, city, country=None, name=None, **kwargs):
        self.lat, self.lng, self.location_dict = lat, lng, self._get_location_dict(lat, lng, city, country, name)
        return self._send_request("PUT", "/v2/users/location", payload={"location": self.location_dict}, **kwargs)

    def create_post(self, message=None, imgpath=None, b64img=None, color=None, ancestor=None, channel="", **kwargs):
        if not imgpath and not message and not b64img:
            raise Exception("One of message or imgpath must not be null.")

        payload = {"color": color if color else random.choice(self.post_colors),
                   "location": self.location_dict,
                   "ancestor": ancestor,
                   "message": message,
                   "channel": channel}
        if imgpath:
            with open(imgpath, "rb") as f:
                imgdata = base64.b64encode(f.read()).decode("utf-8")
                payload["image"] = imgdata
        elif b64img:
            payload["image"] = b64img

        return self._send_request("POST", '/v3/posts/', payload=payload, **kwargs)

    def upvote(self, post_id, **kwargs):
        return self._send_request("PUT", '/v2/posts/%s/upvote/' % post_id, **kwargs)

    def downvote(self, post_id, **kwargs):
        return self._send_request("PUT", '/v2/posts/%s/downvote/' % post_id, **kwargs)

    def give_thanks(self, post_id, **kwargs):
        return self._send_request("POST", '/v3/posts/%s/giveThanks' % post_id, **kwargs)

    def get_post_details(self, message_id, **kwargs):
        return self._send_request("GET", '/v2/posts/%s/' % message_id, **kwargs)

    def get_post_details_v3(self, message_id, skip=0, **kwargs):
        return self._send_request("GET", '/v3/posts/%s/details' % message_id, params={'details': 'true', 'reply': skip}, **kwargs)

    def _get_posts(self, post_types="", skip=0, limit=60, mine=False, hashtag="", channel="", **kwargs):
        category = "mine" if mine else "hashtag" if hashtag else "channel" if channel else "location"
        params = {"lat": self.lat, "lng": self.lng, "skip": skip, "limit": limit, "hashtag": hashtag, "channel": channel}
        url = "/v%s/posts/%s/%s" % ("2" if not (hashtag or channel) else "3", category, post_types)

        return self._send_request("GET", url, params=params, **kwargs)

    def get_share_url(self, post_id, **kwargs):
        return self._send_request("POST", "/v3/posts/%s/share" % post_id, **kwargs)

    def get_notifications(self, **kwargs):
        return self._send_request("PUT", "/v3/user/notifications", **kwargs)

    def get_notifications_new(self, **kwargs):
        return self._send_request("GET", "/v3/user/notifications/new", **kwargs)

    def notification_read(self, post_id=None, notification_id=None, **kwargs):
        if post_id:
            return self._send_request("PUT", "/v3/user/notifications/post/%s/read" % post_id, **kwargs)
        elif notification_id:
            return self._send_request("PUT", "/v3/user/notifications/%s/read" % notification_id, **kwargs)
        else:
            raise Exception("One of post_id or notification_id must not be null.") 

    def pin(self, post_id, **kwargs):
        return self._send_request("PUT", "/v2/posts/%s/pin" % post_id, **kwargs)

    def unpin(self, post_id, **kwargs):
        return self._send_request("PUT", "/v2/posts/%s/unpin" % post_id, **kwargs)

    def enable_notifications(self, post_id, **kwargs):
        return self._send_request("PUT", "/v2/posts/%s/notifications/enable" % post_id, **kwargs)

    def disable_notifications(self, post_id, **kwargs):
        return self._send_request("PUT", "/v2/posts/%s/notifications/disable" % post_id, **kwargs)

    def get_posts_recent(self, skip=0, limit=60, mine=False, hashtag="", channel="", **kwargs):
        return self._get_posts('', skip, limit, mine, hashtag, channel, **kwargs)

    def get_posts_popular(self, skip=0, limit=60, mine=False, hashtag="", channel="", **kwargs):
        return self._get_posts('popular', skip, limit, mine, hashtag, channel, **kwargs)

    def get_posts_discussed(self, skip=0, limit=60, mine=False, hashtag="", channel="", **kwargs):
        return self._get_posts('discussed', skip, limit, mine, hashtag, channel, **kwargs)

    def get_my_pinned_posts(self, skip=0, limit=60, **kwargs):
        return self._get_posts('pinned', skip, limit, True, **kwargs)

    def get_my_replied_posts(self, skip=0, limit=60, **kwargs):
        return self._get_posts('replies', skip, limit, True, **kwargs)

    def get_my_voted_posts(self, skip=0, limit=60, **kwargs):
        return self._get_posts('votes', skip, limit, True, **kwargs)

    def get_recommended_channels(self, **kwargs):
        return self._send_request("GET", "/v3/user/recommendedChannels", **kwargs)

    def get_channel_meta(self, channel, **kwargs):
        return self._send_request("GET", "/v3/user/channelMeta", params={"channel": channel}, **kwargs)

    def follow_channel(self, channel):
        return self._send_request("PUT", "/v3/user/followChannel", params={"channel": channel})

    def unfollow_channel(self, channel):
        return self._send_request("PUT", "/v3/user/unfollowChannel", params={"channel": channel})

    def get_user_config(self, **kwargs):
        return self._send_request("GET", "/v3/user/config", **kwargs)

    def get_karma(self, **kwargs):
        return self._send_request("GET", "/v2/users/karma", **kwargs)

    def delete_post(self, post_id, **kwargs):
        return self._send_request("DELETE", "/v2/posts/%s" % post_id, **kwargs)

    def get_captcha(self, **kwargs):
        return self._send_request("GET", "/v3/user/verification/imageCaptcha", **kwargs)

    def submit_captcha(self, key, answer, **kwargs):
        payload = {'key':key, 'answer':answer}
        return self._send_request("POST", "/v3/user/verification/imageCaptcha", payload=payload, **kwargs)

