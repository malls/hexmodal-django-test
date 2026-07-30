Goal: 

To create a simple Django application that is able to parse an incoming payload from an IoT Device and parse the payload. 

There should be basic Token authentication in this payload.

Your work should be submitted to a Github public repo that we can easily set up locally. If there any setup steps, please include them in a README.md 


Expected Logic:

The project should have two models: a Device model and a Payload model. 

A post request should come into a Django Rest Framework endpoint.

The fCnt field on the payload object should be used to ensure that it is not a duplicate message. 

The data key is Base64 encrypted and should be translated into a Hexadecimal value. 

If the value of the data  is 1, then it should be marked as a passing payload. Otherwise, it should be marked as failing. 

A Payload instance is connected to a Device instance through the devEUI field. 

Each Device should keep track of their latest status value (passing vs. failing)

Payload Example:
```
{
"fCnt": 100,
"devEUI": "abcdabcdabcdabcd",
"data": "AQ==",
 "rxInfo": [
{"gatewayID": "1234123412341234",
"name": "G1","time": "2022-07-19T11:00:00",
"rssi": -57,"loRaSNR": 10}
],
   "txInfo": {"frequency": 86810000,"dr": 5}
}
```