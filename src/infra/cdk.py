#!/usr/bin/env python3
"""
NDNx AWS Infrastructure Bootstrap
Based on hardware specifications from the project design document.
Using Python with Django/Flask for services.
"""

from aws_cdk import (
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    aws_kms as kms,
    aws_elasticache as elasti_cache,
    aws_ssm as ssm,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    CfnOutput,
    RemovalPolicy,
    Stack,
)

from constructs import Construct


class NdnxInfrastructureStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # VPC for the NDNx infrastructure
        vpc = ec2.Vpc(
            self, "NdnxVPC",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE,
                    cidr_mask=24
                )
            ]
        )

        # KMS Keys for Encryption Services
        vpn_encryption_key = kms.Key(
            self, "VpnEncryptionKey",
            description="KMS key for VPN encryption",
            enable_key_rotation=True,
            alias="ndnx/vpn-encryption"
        )

        content_encryption_key = kms.Key(
            self, "ContentEncryptionKey",
            description="KMS key for content encryption",
            enable_key_rotation=True,
            alias="ndnx/content-encryption"
        )

        # VPN Datastore - DynamoDB Table
        vpn_datastore = dynamodb.Table(
            self, "VpnDatastore",
            table_name="ndnx-vpn-users",
            partition_key=dynamodb.Attribute(
                name="userId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="sessionId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.KMS,
            encryption_key=vpn_encryption_key,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Add GSI for efficient querying by user sessions
        vpn_datastore.add_global_secondary_index(
            index_name="UserSessionsIndex",
            partition_key=dynamodb.Attribute(
                name="userId",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # Content Cache - ElastiCache Memcached Cluster
        cache_subnet_group = elasti_cache.CfnSubnetGroup(
            self, "CacheSubnetGroup",
            description="Subnet group for NDNx Content Cache",
            subnet_ids=vpc.private_subnets_subnet_ids
        )

        cache_security_group = ec2.SecurityGroup(
            self, "CacheSecurityGroup",
            vpc=vpc,
            description="Security group for Memcached Content Cache",
            allow_all_outbound=True
        )

        memcached_cache = elasti_cache.CfnCacheCluster(
            self, "NdnxMemcachedCache",
            cache_cluster_id="ndnx-content-cache",
            cache_node_type="cache.t3.micro",
            engine="memcached",
            num_cache_nodes=1,
            port=11211,
            vpc_security_group_ids=[cache_security_group.security_group_id],
            cache_subnet_group_name=cache_subnet_group.ref
        )

        # Security Group for EC2 Instances
        ec2_security_group = ec2.SecurityGroup(
            self, "Ec2SecurityGroup",
            vpc=vpc,
            description="Security group for NDNx EC2 instances",
            allow_all_outbound=True
        )

        # Allow inbound traffic on necessary ports
        ec2_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(22),
            description="Allow SSH access"
        )
        ec2_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP traffic"
        )
        ec2_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS traffic"
        )
        ec2_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(8000),
            description="Allow Django/Flask development server"
        )

        # Allow communication between instances
        ec2_security_group.add_ingress_rule(
            peer=ec2_security_group,
            connection=ec2.Port.all_tcp(),
            description="Allow inter-instance communication"
        )

        # Allow access to cache
        cache_security_group.add_ingress_rule(
            peer=ec2_security_group,
            connection=ec2.Port.tcp(11211),
            description="Allow access from EC2 instances"
        )

        # IAM Role for EC2 instances
        ec2_role = iam.Role(
            self, "NdnxEc2Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonDynamoDBFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSKeyManagementServicePowerUser")
            ]
        )

        # Python/Django User Data script for EC2 instances
        python_user_data = """#!/bin/bash
        yum update -y
        yum install -y python3 python3-pip git nginx

        # Install Python development tools
        pip3 install --upgrade pip
        pip3 install virtualenv

        # Create application directory
        mkdir -p /opt/ndnx
        cd /opt/ndnx

        # Create virtual environment
        python3 -m venv ndnx_env
        source ndnx_env/bin/activate

        # Install Python packages
        pip3 install django flask gunicorn boto3 pymemcache python-memcached

        # Create Django project structure
        cat > requirements.txt << 'EOF'
        Django==4.2.7
        Flask==3.0.0
        gunicorn==21.2.0
        boto3==1.34.0
        python-memcached==1.62
        django-cors-headers==4.3.1
        djangorestframework==3.14.0
        EOF

        # Create Flask application
        cat > app.py << 'EOF'
        import os
        from flask import Flask, jsonify, request
        from flask_cors import CORS
        import boto3
        from pymemcache.client.base import Client as MemcacheClient
        import json
        from datetime import datetime

        app = Flask(__name__)
        CORS(app)

        # AWS SDK configuration
        aws_region = os.environ.get('AWS_REGION', 'us-east-1')
        dynamodb = boto3.resource('dynamodb', region_name=aws_region)
        kms = boto3.client('kms', region_name=aws_region)

        # Initialize DynamoDB table
        vpn_table = dynamodb.Table('ndnx-vpn-users')

        # Initialize Memcached client
        cache_endpoint = os.environ.get('CACHE_ENDPOINT', 'localhost:11211')
        memcache_client = MemcacheClient(cache_endpoint.split(':'))

        @app.route('/health', methods=['GET'])
        def health_check():
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat(),
                'service': os.environ.get('SERVICE_TYPE', 'unknown')
            })

        @app.route('/api/users/<user_id>', methods=['GET'])
        def get_user(user_id):
            try:
                response = vpn_table.query(
                    KeyConditionExpression=boto3.dynamodb.conditions.Key('userId').eq(user_id)
                )
                return jsonify(response)
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @app.route('/api/users', methods=['POST'])
        def create_user():
            try:
                data = request.json
                data['createdAt'] = datetime.utcnow().isoformat()
                vpn_table.put_item(Item=data)
                return jsonify({'message': 'User created successfully'})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @app.route('/api/content/<content_id>', methods=['GET'])
        def get_content(content_id):
            try:
                # Check Memcached first
                cached_content = memcache_client.get(content_id)
                if cached_content:
                    return jsonify({
                        'contentId': content_id,
                        'content': cached_content.decode('utf-8'),
                        'source': 'cache'
                    })

                # If not in cache, return placeholder
                return jsonify({
                    'contentId': content_id,
                    'message': 'Content service placeholder',
                    'source': 'database'
                })
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @app.route('/api/cache/<content_id>', methods=['POST'])
        def cache_content(content_id):
            try:
                data = request.json
                content = data.get('content', '')
                memcache_client.set(content_id, content)
                return jsonify({'message': 'Content cached successfully'})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        if __name__ == '__main__':
            app.run(host='0.0.0.0', port=8000, debug=True)
        EOF

        # Create Django project (optional alternative)
        cat > django_app.py << 'EOF'
        import os
        import django
        from django.conf import settings
        from django.http import JsonResponse
        from django.views.decorators.csrf import csrf_exempt
        from django.views.decorators.http import require_http_methods
        from django.views import View
        import boto3
        import json

        # Configure Django settings
        if not settings.configured:
            settings.configure(
                DEBUG=True,
                SECRET_KEY='ndnx-secret-key-placeholder',
                ALLOWED_HOSTS=['*'],
                CORS_ALLOW_ALL_ORIGINS=True,
            )
            django.setup()

        class HealthCheckView(View):
            def get(self, request):
                return JsonResponse({
                    'status': 'healthy',
                    'service': 'django',
                    'timestamp': django.utils.timezone.now().isoformat()
                })

        @csrf_exempt
        @require_http_methods(["GET", "POST"])
        def user_api(request, user_id=None):
            aws_region = os.environ.get('AWS_REGION', 'us-east-1')
            dynamodb = boto3.resource('dynamodb', region_name=aws_region)
            vpn_table = dynamodb.Table('ndnx-vpn-users')

            if request.method == 'GET' and user_id:
                try:
                    response = vpn_table.query(
                        KeyConditionExpression=boto3.dynamodb.conditions.Key('userId').eq(user_id)
                    )
                    return JsonResponse(response)
                except Exception as e:
                    return JsonResponse({'error': str(e)}, status=500)

            elif request.method == 'POST':
                try:
                    data = json.loads(request.body)
                    data['createdAt'] = django.utils.timezone.now().isoformat()
                    vpn_table.put_item(Item=data)
                    return JsonResponse({'message': 'User created successfully'})
                except Exception as e:
                    return JsonResponse({'error': str(e)}, status=500)

            return JsonResponse({'error': 'Invalid request'}, status=400)
        EOF

        # Create systemd service for Flask
        cat > /etc/systemd/system/ndnx-flask.service << 'EOF'
        [Unit]
        Description=NDNx Flask Service
        After=network.target

        [Service]
        Type=simple
        User=root
        WorkingDirectory=/opt/ndnx
        ExecStart=/opt/ndnx/ndnx_env/bin/python app.py
        Restart=always
        RestartSec=10
        Environment=AWS_REGION=us-east-1
        Environment=SERVICE_TYPE=flask

        [Install]
        WantedBy=multi-user.target
        EOF

        # Create systemd service for Django (alternative)
        cat > /etc/systemd/system/ndnx-django.service << 'EOF'
        [Unit]
        Description=NDNx Django Service
        After=network.target

        [Service]
        Type=simple
        User=root
        WorkingDirectory=/opt/ndnx
        ExecStart=/opt/ndnx/ndnx_env/bin/python django_app.py
        Restart=always
        RestartSec=10
        Environment=AWS_REGION=us-east-1
        Environment=SERVICE_TYPE=django

        [Install]
        WantedBy=multi-user.target
        EOF

        systemctl daemon-reload

        # Create nginx configuration
        cat > /etc/nginx/conf.d/ndnx.conf << 'EOF'
        server {
            listen 80;
            server_name _;

            location / {
                proxy_pass http://127.0.0.1:8000;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
            }
        }
        EOF

        systemctl enable nginx
        systemctl start nginx

        # Determine service type based on instance role
        if [[ $(hostname) == *"user-device"* ]]; then
          echo "export SERVICE_TYPE=user-device" >> /etc/environment
          systemctl start ndnx-flask.service
        elif [[ $(hostname) == *"vpn-server"* ]]; then
          echo "export SERVICE_TYPE=vpn-server" >> /etc/environment
          systemctl start ndnx-django.service
        fi
        """

        # Amazon Linux 2 AMI
        amazon_linux_ami = ec2.MachineImage.latest_amazon_linux(
            generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
        )

        # User Device EC2 Instance (Entrypoint) - Flask
        user_device_instance = ec2.Instance(
            self, "UserDeviceInstance",
            vpc=vpc,
            instance_type=ec2.InstanceType("t3.medium"),
            machine_image=amazon_linux_ami,
            user_data=ec2.UserData.custom(python_user_data),
            role=ec2_role,
            security_group=ec2_security_group,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(
                        volume_size=20,
                        encrypted=True,
                        delete_on_termination=True
                    )
                )
            ]
        )

        # VPN Server EC2 Instance - Django
        vpn_server_instance = ec2.Instance(
            self, "VpnServerInstance",
            vpc=vpc,
            instance_type=ec2.InstanceType("t3.large"),
            machine_image=amazon_linux_ami,
            user_data=ec2.UserData.custom(python_user_data),
            role=ec2_role,
            security_group=ec2_security_group,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(
                        volume_size=30,
                        encrypted=True,
                        delete_on_termination=True
                    )
                )
            ]
        )

        # Application Load Balancer for handling traffic
        alb = elbv2.ApplicationLoadBalancer(
            self, "NdnxALB",
            vpc=vpc,
            internet_facing=True,
            security_group=ec2_security_group
        )

        listener = alb.add_listener(
            "Listener",
            port=80,
            open=True
        )

        target_group = listener.add_targets(
            "Fleet",
            port=8000,
            targets=[user_device_instance]
        )

        # SSM Parameters for configuration
        ssm.StringParameter(
            self, "VpnDatastoreTableName",
            parameter_name="/ndnx/vpn/datastore/table_name",
            string_value=vpn_datastore.table_name,
            description="DynamoDB table name for VPN datastore"
        )

        ssm.StringParameter(
            self, "ContentCacheEndpoint",
            parameter_name="/ndnx/content/cache/endpoint",
            string_value=f"{memcached_cache.attr_configuration_endpoint_address}:11211",
            description="Memcached endpoint for content cache"
        )

        ssm.StringParameter(
            self, "VpnEncryptionKeyArn",
            parameter_name="/ndnx/vpn/encryption/key/arn",
            string_value=vpn_encryption_key.key_arn,
            description="ARN of VPN encryption KMS key"
        )

        ssm.StringParameter(
            self, "ContentEncryptionKeyArn",
            parameter_name="/ndnx/content/encryption/key/arn",
            string_value=content_encryption_key.key_arn,
            description="ARN of content encryption KMS key"
        )

        # CloudWatch Log Groups
        log_group = logs.LogGroup(
            self, "NdnxLogGroup",
            log_group_name="/aws/ndnx/python-service",
            retention=logs.RetentionDays.ONE_WEEK
        )

        # Outputs
        CfnOutput(
            self, "UserDeviceInstanceId",
            value=user_device_instance.instance_id,
            description="Instance ID of User Device (Flask API)"
        )

        CfnOutput(
            self, "VpnServerInstanceId",
            value=vpn_server_instance.instance_id,
            description="Instance ID of VPN Server (Django API)"
        )

        CfnOutput(
            self, "VpnDatastoreTable",
            value=vpn_datastore.table_name,
            description="DynamoDB table name for VPN user data"
        )

        CfnOutput(
            self, "ContentCacheEndpoint",
            value=f"{memcached_cache.attr_configuration_endpoint_address}:11211",
            description="Memcached cluster endpoint"
        )

        CfnOutput(
            self, "LoadBalancerDNS",
            value=alb.load_balancer_dns_name,
            description="ALB DNS name for accessing the services"
        )


# Import statements at the top of your CDK app file
from aws_cdk import App, Aws, aws_logs as logs, aws_elasticloadbalancingv2 as elbv2

app = App()
NdnxInfrastructureStack(
    app,
    "NdnxInfrastructure",
    env={
        'account': Aws.ACCOUNT_ID,
        'region': Aws.REGION
    }
)
app.synth()