# Jodel API

[![Build Status](https://travis-ci.org/nborrmann/jodel_api.svg?branch=master)](https://travis-ci.org/nborrmann/jodel_api) [![Coverage Status](https://img.shields.io/codecov/c/github/nborrmann/jodel_api.svg)](https://codecov.io/gh/nborrmann/jodel_api)

Inofficial interface to the private API of the Jodel App. Not affiliated with *The Jodel Venture GmbH*.

## Usage

### Account Creation

Calling the bare constructor creates a new account:
```python
>>> import jodel_api
>>> lat, lng, city = 48.148434, 11.567867, "Munich"
>>> j = jodel_api.JodelAccount(lat=lat, lng=lng, city=city)
Creating new account.
```
`get_account_data()` returns all data associated with this account (censored by me):
```python
>>> j.get_account_data()
{'access_token': 'xxx', 'expiration_date': 1472660000, 'refresh_token': 'xxx', 'distinct_id': 'xxx', 'device_uid': 'xxx'}
```

Save this data to reuse the account later on, feed it to the JodelAccount() constructor to reinitiate the account. This constructor issues one request to update the location of the account.
```python
>>> j = jodel_api.JodelAccount(lat=lat, lng=lng, city=city, access_token='xxx', expiration_date='xxx', 
                               refresh_token='xxx', distinct_id='xxx', device_uid='xxx')
(204, '')
```

Add `update_location=False` to suppress this behaviour. The constructor will only instantiate an object, without making any remote calls:
```python
>>> j = jodel_api.JodelAccount(lat=lat, lng=lng, city=city, update_location=False, **account_data)
```

For some functionality (look out for error 478) accounts need to be verified by entering a captcha:
```python
>>> j.verify_account()
https://s3-eu-west-1.amazonaws.com/jodel-image-captcha/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.png
Open the url above in a browser and enter the images containing a racoon (left to right, starting with 0) separated by spaces: 3 5
Verification failed. Retrying ...
https://s3-eu-west-1.amazonaws.com/jodel-image-captcha/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.png
Open the url above in a browser and enter the images containing a racoon (left to right, starting with 0) separated by spaces: 0 3 7
Account successfully verified.
>>> j.verify_acccount()
Account is already verified.
```
After `expiration_date` has passed, call `refresh_access_tokens()` to re-authenticate. If `refresh_access_token` fails, use `refresh_all_tokens` instead (this is akin to creating a new account, but preserves the account's data (karma, etc)):
```python
>>> j.refresh_access_token()
(200, {'token_type': 'bearer', 'access_token': 'xxx', 'expires_in': 604800, 'expiration_date': xxx})
>>> j.refresh_all_tokens()
(200, {'expires_in': 604800, 'access_token': 'xxx', 'token_type': 'bearer', 'returning': True, 'refresh_token': 'xxx', 'expiration_date': 1472600000, 'distinct_id': 'xxx'})
```

### API calls

All remote API calls return a tuple of HTTP status_code and the response (if possible a dict, parsed from the API response), but might also be a string (error message).

The following API calls are supported (presented without their respective responses):
```python
>>> j.set_location(lat, lng, city, country=None, name=None) # country and name appear to have no effect
>>> j.create_post(message=None, imgpath=None, color=None, ancestor=None, channel="")
>>> j.get_post_details(post_id)
>>> j.get_post_details_v3(post_id, skip=0) # This api endpoint implements paging and returns at most 50 replies, use the skip parameter to page through the thread. 
>>> j.upvote(post_id)
>>> j.downvote(post_id)
>>> j.pin(post_id)
>>> j.unpin(post_id)
>>> j.enable_notifications(post_id)
>>> j.disable_notifications(post_id)
>>> j.give_thanks(post_id)
>>> j.get_share_url(post_id)
>>> j.delete_post(post_id) # Only works on your own posts ಠ_ಠ
>>> j.get_notifications()
>>> j.get_notifications_new()
>>> j.notification_read(post_id=None, notification_id=None)
>>> j.get_recommended_channels()
>>> j.get_channel_meta(channel)
>>> j.follow_channel(channel)
>>> j.unfollow_channel(channel)
>>> j.get_user_config()
>>> j.get_karma()
```

The following calls can be used to read posts. The arguments `mine` (boolean), `hashtag`, `channel` (both strings) are exclusive. If `mine` evaluates to `true`, the other two arguments are discarded, if `hashtag` evaluates `true` , `channel` is discarded. 
```python
>>> j.get_posts_recent(skip=0, limit=60, mine=False, hashtag="", channel="")
>>> j.get_posts_popular(skip=0, limit=60, mine=False, hashtag="", channel="")
>>> j.get_posts_discussed(skip=0, limit=60, mine=False, hashtag="", channel="")
>>> j.get_my_pinned_posts(skip=0, limit=60)
>>> j.get_my_replied_posts(skip=0, limit=60)
>>> j.get_my_voted_posts(skip=0, limit=60)
```

You can pass additional arguments (such as proxies and timeouts) to all API calls through the `**xargs` argument that will be passed to the `requests.request()` function:
```python
>>> j.upvote(post_id, timeout=5, proxies={'https': '127.0.0.1:5000'})
```

### Error Codes

 - **429 "Too Many Requests"**: Your IP is rate-limited.
 - **477 "Signed Request Expected"**: This library should handle request signing. If this happens on the latest version of `jodel_api` there is a bug in this library. Please open an issue.
 - **478 "Account not verified"**: Solve the captcha challenge (eg. through `verify_account()`).
 - **502 "Bad Gateway"**:  Something went wrong server-side. This happens pretty randomly. `jodel_api` automatically retries two times when it sees this error. If you encounter this status, the jodel servers are probably having issues. Try again later.

### Tests

Nearly all tests in `jodel_api_test.py` are integration tests, which means they actually hit the Jodel servers. These can fail for any number of reasons (eg. connectivity issues), which does not necessarily imply there is something wrong with this library. As this library tries to make few assumptions about the content of the json responses they test mostly for status codes, not the contents of the responses (ie. they test whether the API endpoints are still valid).

For the tests in `class TestUnverifiedAccount` a new account is created on every run and they test read-only functions for which the account does not need to be verified. Tests in `class TestVerifiedAccount` reuse the same already verified account to test voting and creating posts. Please do not run these unnecessarily as the account might get banned. If you need the tests, overwrite the account-data to use our own verfied account.

Run the tests with

```pytest -v jodel_api_test.py::TestUnverifiedAccount```

## Rate-Limits

The Jodel API appears to have the following (IP-based) rate-limits

- max of 60 new account registrations from one IP per half hour
- max of 200 (?) votes (possibly also post creations?) in an unknown time frame

They also hand out perma-bans if you overdo it.
