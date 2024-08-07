---
Title: 파이콘 한국의 AWS 비용을 줄여보기
Date: 2024-07-17 22:00
Slug: aws-cost-optimization-pycon-kr
Tags: aws
Lang: ko
Summary: How to Optimize PyCon Korea AWS Spending
---

## 파이콘 한국의 AWS 비용을 줄여보기

파이콘 한국은 AWS를 사용하여 서비스를 제공하고 있습니다.

### 파이콘 한국 웹  서비스의 역사

파이콘 한국은 2014년에 시작되었습니다. 4년은 Naver Cloud 에서 서비스를 제공받았습니다. 아직도 남아 있고 비용을 내고 있습니다만  그후에 AWS 가 대중화되었기 때문에 신규 서비스는 AWS  를 사용하고 있습니다.

### 왜 문제인가?

파이콘 한국은 매년 준비 위원회를 뽑습니다.  준비 위원회는 많은 분들이 개발자거나 개발자 출신입니다. 그래서 파이콘 한국의 모든 웹 서비스 스택은 매년 바뀌는 전통을 가지고 있습니다. 물론 백엔드는 기본적으로 django 입니다만 프론트엔드는 계속 바뀌고 있습니다. Django 의 경우도 웹서비스를 전부 제공하는 경우도 있고 restapi 를 제공하거나 또는 graphql 을 제공하기도 했습니다. 하지만 제일 중요한 점은 인원이 계속 바뀜으로서 기술 스택이 계속 바뀌었다는 점입니다.

### 그래서 어떤 것이 문제인가?

어느날 파이콘 한국의 AWS 비용이 한달에  100만원을 넘었습니다. 물론 몇번의 시도는 있었지만 파이콘 준비위원회는 다들 바쁘고 경력이 있는 지원자들도 바쁘다보니 많은 시간을 들이진 못했습니다. 그래서 AWS 비용을 줄이기 위한 시도는 계속 실패했습니다.

### 그래서 어떻게 했나?

#### 1.  많은 비용을 쓰는 것과 쉬운 것부터 처리하는 원칙

AWS 의 비용은 매우 복잡합니다. 그래서 먼저 비용을 확인해보고 가장 많은 비용을 쓰는 것과  비용을 줄이는 것이 쉬운 것부터 처리하자는 생각을 했습니다.

파이콘 한국의 특성상 매년 이벤트용 서비스가 아니라면 사실상 다운타임이 있어도 상관없습니다. 물론 스태틱으로 만드는 것이 제일 좋지만 아직까지 그럴 여유가 없습니다. 그래서 지난 이벤트용 서비스는 다운타임이 있어도 상관없다는 것을 이용하여 비용을 줄이기로 했습니다.

#### 2. ALB, subnet 과 ip 를 줄이자

도메인이 바뀌는 만큼 ALB 를 많이 사용하게 되었습니다. 그래서 ALB 를 줄이기로 했습니다.

ALB 는 서비스 하나에 고가용성을 위한 subnet 갯수만큼 ip 를 사용합니다.

ALB 는 합치고 Rule 을 이용해서 라우팅을 하기로 했습니다.  보통 도메인과 패스를 이용하면 합쳐도 문제가 없기 때문이 것을 이용하기로 했습니다.

그래서 9개였던 ALB 를 4개로 줄였습니다.

서브넷도 3개이던것을 2개로 줄였습니다.

그러면 1개의 ALB 는 2개의 서브넷을 사용하므로 총 사용되는 ip 는 8개가 되게 됩니다. 기존에는 27개였기 때문에 19개를 줄일 수 있게 되었습니다.

ECS 의 경우도 외부와 통신을 한다면 공인 ip 를 요청해서 받게됩니다. 해당 옵션을 모두 끄고 nat gateway 를 이용하여 통신하게 했습니다.
여기서도 6개에서 12개의 ip 를 줄였습니다.

#### 3. ECS 의 비용을 줄이자 1

ECS 는 기본적으로 Fargate 를 사용하고 있습니다. Fargate 는 사용한 만큼 비용을 내야하는데 Spot 설정이 안되어있었습니다. 그럼 왜 안했을가? 를 고민해보게 되는데 알고보니 대부분의 이미지가 개발을 위주로 하여 만들어졌기 때문에 기동을 하면 서비스를 바로 제공하지 않고 설정을 하거나 컴파일을 하거나 하는 과정들이 있었습니다. 그래서 Spot 을 설정할경우에 기동이 안되는 문제가 생기는 것을 확인했습니다.

그럼 어떻게 해야하나? 일단 Docker Image 를 한땀 한땀 수정해서 기동이 바로 되도록 했습니다.

주로 설정한 것은 다음과 같습니다.

- 과도한 worker 설정 수정 <https://github.com/pythonkr/pyconkr-2019-api/commit/c898ea6b6624df243de48f72b31d4cd7d48f0d8f>
- 기동시 말고 docker 빌드시에 next build 설정 <https://github.com/pythonkr/pyconkr-2023-frontend/commit/d3a6c41f87c9f9b97be008c6ef95a48ca71529cf>
- 도메인 변경에 맞춰서 설정 변경
- CI 가 깨진경우라도 CI  를 고치지 않고 빌드를 로컬에서 하여 푸쉬

#### 4. ECS 의 비용을 줄이자 2

ECS 는 task definition 을 이용하여 설정을 합니다. 그래서 서비스를 추가하고 돌리면서 내리면서 메모리와 CPU 를 조정하였습니다.

그리고 ECS 의 용량공급자를 이용해서 Auto Scaling Group 을 모두 Spot 으로 연결했습니다. 어차피 조금은 죽어도 된다고 생각했고 전혀 문제 없이 동작합니다.

#### 5. CloudWatch 와 ECR 비용 줄이기

CloudWatch 와 ECR 모두 마찬가지인데 AWS 에 기능이 계속 추가되고 기본값이 바뀌면서 서비스를 사용했기 때문에 오래된 서비스들에는 retention 설정이 안되어있었습니다. 그래서 삭제가 안되던것을 확인하고 수동으로 삭제후에 retention 을 지정했습니다.

#### 6. RDS 용량 줄이기

아마존은 Serverless 라는 환상을 줬습니다. 물론 람다는 훌륭하고 애정하지만 RDS Serverless 를 사용하면 비용이 많이 들수밖에 없습니다. 다행히 Serverless 니까 용량을 줄이는 것만으로 비용이 줍니다. 설정을 보고 용량을 조정했습니다.

#### 그래서 얼마나 줄었나?

기존에는 하루에 25불이었던 비용이 14불로 줄었습니다. 최종적으로는 7불정도로 줄일 수 있을 것으로 예상됩니다.

#### 추후 할일

- RDS 를 하나로 통합하기
- 이미지를 모두 arm 으로 빌드하여 arm 인스턴스로 변경하기
- 최종적으로는 Static Site 가 되도록 만들기
- nat gateway 를 없애고 headscale 설치한 nat instance 를 ASG 로 제공하기
  - <https://github.com/chime/terraform-aws-alternat>
  - <https://github.com/fonzcastellanos/cdk-nat-asg-provider>
  - <https://blog.data-ish.info/general/nat-auto-scaling-group.html>
  - <https://medium.com/journey-through-the-cloud/high-availability-nat-with-sns-and-lambda-a85de04a7e76>








