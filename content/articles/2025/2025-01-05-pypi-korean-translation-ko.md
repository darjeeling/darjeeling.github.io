---
Title: 물은 100도에서 끓고 번역은 100%가 되어야 끝납니다.
Date: 2025-01-05 13:00
Category: Python
Slug: pypi-translated-ko
Tags: python
Lang: ko
Summary:  PyPI warehouse 한국어 번역이 100%  를 달성하여, PyPI 웹사이트에 한국어 번역이 추가되었습니다.
---

## PyPI warehouse 한국어 번역이 100% 달성

2024년 12월 25일 크리스마스, [PyPI warehouse의 한국어 번역이 대망의 100%]( https://github.com/pypi/warehouse/pull/17326) 를 달성했습니다. PyPI의 웹사이트를 구현한 이 프로젝트는 이제 한국어로 서비스되며, PyPI.org 하단 우측의 언어 선택에서 한국어를 선택하여 사용하실 수 있습니다.

5년 전 [scari님이 시작한 번역 프로젝트](https://hosted.weblate.org/changes/browse/pypa/warehouse/ko/?page=207&limit=20)가 마침내 결실을 맺은 것입니다. 1,608개에 달하는 방대한 문자열의 번역 작업에 참여해주신 모든 분들께 깊은 감사를 드립니다. 영어 사용에 능숙한 분들도 많겠으나, 이번 한국어화를 통해 더 많은 사람들이 PyPI를 편리하게 이용할 수 있게 되었습니다.

작년에 [이준원님](https://github.com/cpprhtn) 에게 번역을 요청하면서 저의 짐작으로는 65% 쯤 되면 사이트에 노출이 될것이라고 생각하고 격려했는데 100% 가 되어야 한다고 해서 개인적으로 좌절하고 조금씩하다가 잊고 있었습니다. 하지만 준원님이 결국 끝까지 해내고 100%를 달성했습니다. 감사합니다. 번역관련 기여를 해보고 싶으신 분은  [준원님의 레포](https://github.com/cpprhtn/pypi-Korean-Translations) 를 참조해주세요.

마치 물이 정확히 100도에서 끓는 것처럼, 번역 또한 100% 완성되어야 비로소 그 가치를 발휘할 수 있습니다. 하지만 파이썬 생태계에는 아직도 번역이 필요한 많은 부분이 남아있습니다.

* [django 번역](https://explore.transifex.com/django/django/) - 98% 이므로 조금만 하면 됩니다.
* [django 문서 번역](https://explore.transifex.com/django/django-docs/) -  현재 18% 번역되어 있습니다
* [django gurls tutorial 번역](https://crowdin.com/project/django-girls-tutorial) - 92% 번역되어 있습니다.
* [python 공식 문서 한국어 번역](https://devguide.python.org/documentation/translating/) - 3.9 까지 번역되어 있습니다.
* 이 외에도 많은 부분이 번역이 필요하지만 생각나는 부분만 적었습니다. 알려주시면 리스트에 추가하겠습니다.

### pypi warehouse 한국어 번역 상위 10위

![pypi 한국어 번역 상위 10위]({static}/images/pypi_translation_user_activity_ranking.png)

### pypi warehouse 한국어 번역 상위 10위 사용자 활동 추이

![pypi 한국어 번역 상위 10위 사용자 활동 추이]({static}/images/pypi_translation_top10_user_activity_trends.png)

## 번역에 기여하신분

| ID |Activity Count|
|:-------|-------:|
|cpprhtn        |  730|
|lqez           |  422|
|darjeeling     |  172|
|earthyoung     |   87|
|OHvrything     |   63|
|kkumtree       |   63|
|choo121600     |   56|
|Coalery        |   49|
|Dongseop       |   42|
|minho42        |   35|
|Tanat05        |   21|
|alpakaka0o0    |   18|
|kijk2869       |   15|
|Parannarae     |   13|
|ihwan          |   11|
|proost         |   10|
|XuZhuoHan2009  |    9|
|emscb          |    7|
|scari          |    7|
|leejs209       |    6|
|mylovercorea   |    6|
|anonymous      |    6|
|semi-yu        |    4|
|hyungjin8943   |    4|
|di             |    4|
|bunseokbot     |    4|
|rlawn1         |    4|
|kms1212        |    3|
|wckim          |    2|
|joonykim       |    2|
|ewdurbin       |    1|

## Python 에 기여하는 방법

### PSF 와 파이썬사용자모임에 기부하기

* PSF 에 [서포팅 회원](https://www.python.org/psf/membership/supporting/)으로 가입합니다. ( 1년 100불 )
* 혹은 [PSF 의 github](https://github.com/sponsors/psf) 에서 기부도 가능합니다. ( 1달에 최소 1달러 부터 가능 )

### 파이썬사용자모임에 기여하기

파이썬사용자모임은 파이콘한국과 각종 파이썬모임을 운영하고 있습니다.
기여를 통하여 한국의 파이썬 커뮤니티를 지원가능합니다.

* [파이썬 사용자 모임의  github](https://github.com/sponsors/pythonkr) 에서 기부를 받을수 있습니다.
* 파이썬 관련 발표나 튜토리얼을 준비하거나, 봉사활동을 통하여 기여할 수 있습니다.
* 올해 공익법인으로 전환예정입니다.
* 파이콘 한국 2025는 8월예 예정되어있으며 장소선정을 위하여 논의중입니다. 서울시내 대학교를 예정하고 있으며 공간후원을 받고 있습니다. 관심있으신 곳은 연락주시면 좋겠습니다.

### 파이썬 개별 프로젝트에 기여하기

* django, fastapi 등 많은 파이썬 프로젝트가 있습니다.
* 기여가 어렵다면 <https://djangonaut.space/> 같은곳에서 기여하는법을 배울수 있습니다.

### Python Asia Origanization 에 창립회사로 기부하기

* 아시아의 파이썬 커뮤니티를 지원하기 위하여 작년에 설립된 비영리 법인입니다.
* 후원을 하고 싶으신 회사는 board@pythonasia.org 로 메일을 주시면 후원사 킷을 보내어드리겠습니다.

### 발표하기

* 본인이 파이썬으로 무엇을 만들었는지, 어떤 경험을 했는지 발표하면 됩니다.
* 완벽할 필요도 없고, 영어로 할 필요도 없습니다. 어떤 분야든 발표가 가능합니다.

## 마치며

* 번역에 참여한 모든 분들에게 감사드립니다.
* 파이썬은 누구나 참여할 수 있는 오픈소스 프로젝트입니다.
* 파이썬을 사용하면서 불편한 점이나 개선할 점이 있다면 이슈를 올리거나 PR을 보내주세요.
* 다른 형태의 기여를 하고 싶다면 연락주세요.
