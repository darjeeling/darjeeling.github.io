---
Title: 지금이 Free Threading Python에 기여하기 좋은 시점입니다
Date: 2025-05-20 08:00
Category: Python
Slug: free-threading-pyconus2025
Tags: python, free-threading, pyconus2025
Lang: ko
Summary:  time to contribute to Free Threading Python
---

## 지금이 Free Threading Python에 기여하기 좋은 시점입니다

파이콘 US 2025 에서 현재까지 파악한 Free Threading Python에 대해서 간단하게 정리해보고 기여에 대해서 정리해보겠습니다.

## Free Threading Python이란?

Free Threading Python은 파이썬의 GIL(Global Interpreter Lock)을 제거하여 멀티스레드 환경에서 성능을 향상시키는 것을 목표로 하는 프로젝트입니다. 이 프로젝트는 파이썬의 멀티스레딩 성능을 개선하고, CPU 바운드 작업에서 더 나은 성능을 제공하기 위해 시작되었습니다.

아직은 실험적인 단계에 있으며, 컴파일을 다시 해서 설치하거나 uv 를 통해서 설치해야합니다.

## 현재 상황

저도 테스트만 해보고 있으나 대부분의 순수 파이썬 라이브러리는 사용에 문제가 없다고합니다. 하지만 대부분이 보편적으로 사용하는 라이브러리들은 성능이나 구현문제로 C/C++ 로된 라이브러리를 불러오거나 직접 확장으로 구현해서 사용하기 때문에 이런 라이브러리들은 Free Threading Python을 사용하려면 여러 방안을 써야합니다.

### 확장 모듈을 사용하는 경우

대부분 다음의 방법들을 사용하고 [포팅 가이드](https://py-free-threading.github.io/porting-extensions/)가 있습니다.

- C API
- Cython
- PyBind11
- nanonbind
- PyO3
- f2py

CFFI 는 아직 지원하지 않지만 [쿼트싸이트의 fork](https://github.com/Quansight-Labs/cffi) 를 사용해서 지원이 가능합니다.
[지원을 하지 않겠다는 이슈](https://github.com/python-cffi/cffi/issues/119)는 있는데 CFFI 는 대부분 인터페이싱으로 사용하기 때문에 이해는 되는 결정입니다. 포크된 CFFI  를 사용하면 Free Threading Python을 사용할 수 있지만 세밀한 구현은 아니라서 성능은 떨어질것 같습니다.

## 기여하는 방법

여기부터는 깊은 구덩이에 몸을 던지는것 같지만 스프린트에 참여했을때는 모두 긍정적이어서 아직까지는 기여하기 좋은 시점인것 같습니다. 기여하는 방법은 다음과 같습니다.

### 다음을 참조해서 free-threading-python 호환이 잘되는지 확인합니다

- [Free-threaded Python Library Compatibility Checker](https://ft-checker.com/) - 나동희님 제작
- [🧵 Free-Threaded Wheels](https://hugovk.github.io/free-threaded-wheels/)
- [Compatibility Status Tracking#](https://py-free-threading.github.io/tracking/)

### 테스트 후에 이슈를  등록합니다

3.13 free-threading python 을 먼저설치하고 라이브러리를 설치후에 테스트를 돌려봅니다.
가능하면 3.14t 버젼도 해보면 좋겠지만 아직은 베타라서 3.13 버젼을 먼저 해보시는게 좋습니다.

### 포팅을 해서 PR을 날립니다

여기서부터는 조금 어렵습니다. 멀티쓰레드와 여러가지 시스템 콜, 그리고 C/C++ 과 파이썬의 내부에 대한 어느정도 이해가 필요합니다.
가장 어려운 점은 라이브러리들이 서로 의존성이 있는 경우가 많아서 다른 라이브러리들을 쓰는데 해당 라이브러리가 아직 지원을 하지 않는 다면 거기부터 해야합니다.

저도 스프린트에 참가하면서 파악정도만 했는데 이런식이 됩니다.

- fastapi -> uvicorn -> uvloop,  cryptography, pycares

### 기여하는 방법에 대한 글을 씁니다

제가 지금 하고 있습니다만 부족하겠죠. 글을 써서 여러군데 올려봅시다.

### free-threading-python 에 대한 사용법을 씁니다

한국로된 글이 모자라기 떄문에 성능테스트를 하고 사용법을 쓰고 정리를 해서 글로 올려주는 것이 좋습니다.

## 왜 지금 기여해야하는가에 대해서

저는 오픈소스생태계에 있은지가 대략 25년이 좀 넘은것 같습니다. 저는 대단한 오픈소스 기여자가 아니지만 지인들은 많이 기여를 하고 CPython Core Developer 도 두명이나 있고 기타등등 많습니다. 이 때문에 이분들과 이야기를 하면서 생긴 촉이 있습니다.

아무것도 없거나 대격변 시기에 기여를 하는것이 좋습니다. 예를 들면 Python 초기에 기여하신 장혜식님은 다른것도 많이 하셨지만 unicode 나 한글 코덱등을 하셨습니다. 그때는 아무것도 없었고 주여 기여자들이 한글 코덱을 모르기 때문에 비교적 접근이 쉬웠을것으로 생각을 합니다. 그리고 그 다음 변혁은 python3 로 넘어올때였습니다. 그 이후에는 asyncio 쪽이고 이쪽은 김준기님이 기억에 남고 또 다른 분들도 많습니다. 자 이제 또 새로운 기능인 free-threading 이 나왔습니다. 나동희님이 매우 많이 기여를 하시고 있습니다. 저는 지금이 기여에 가장 좋은 시기라고 생각합니다.

다른 언어들의 경우 회사에서 결정하거나 이미 큰 기업이 관리하는 프레임워크에서 변경을 만들기 때문에 쉽지가 않습니다. 물론 파이썬도 매우 접근이 쉬운것은 아닙니다만 수많은 라이브러리와 프레임워크들이 존재하고 지금은 하나씩 모두 포팅이 가능하고 많은 인력이 필요하기 떄문에 지금이 그 시기입니다.

어려운 부분들은 이미 코어나 주요기여자들이 대부분 해결을 했다고 생각합니다. 앞으로 2~3년은 이런 기여가 가능할것으로 생각합니다. 그리고 이 시기를 놓치면 다시는 이런 기회가 오려면 쉽지 않을것 같습니다.
