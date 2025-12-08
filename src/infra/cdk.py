import os

from aws_cdk import App, Environment, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3_assets as s3_assets
from constructs import Construct

ASSET_KEY = os.getenv("ndnx_asset_key")
CONTENT_KEY = os.getenv("ndnx_content_key")
CDN_URL = os.getenv("ndnx_qa_cdn_url")
ENCRYPTED_CONTENT_KEY = os.getenv("ndnx_encrypted_content_key")
NDNX_CONTENT_CACHE = os.getenv("ndnx_qa_content_cache")
QA_KEY = os.getenv("ndnx_qa_key")

# ----------------------------------------------------------------------
# VPN Service Stack – Creates servers for the VPN service and NDNx Cache
# and deploys both. It also creates various AWS infra required for them
# to receive and handle traffic.
# ----------------------------------------------------------------------


class VpnServiceStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # VPC for the VPN Service
        vpc = ec2.Vpc(
            self,
            "VpnVpc",
            max_azs=1,  # Only 1 AZ – keeps costs low
            nat_gateways=0,  # No NAT – instance can reach the internet via public IP
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="VpnVPCPublicSubnet",
                    subnet_type=ec2.SubnetType.PUBLIC,
                ),
            ],
        )

        # Security Group for NDNx Cache server
        self.ndnx_cache_sg = ec2.SecurityGroup(
            self,
            "NDNxCacheSG",
            vpc=vpc,
            description="Security Group for VPN service",
            allow_all_outbound=True,
        )
        # For ease in cross-region requests and since these servers are short lived, full ingress is allowed.
        self.ndnx_cache_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(8000),
            "Allow requests over 8000 from anywhere",
        )

        # put service code in s3 for deployment
        current_directory = os.getcwd()
        repo_directory = os.path.abspath(
            os.path.join(current_directory, os.path.pardir)
        )
        ndnx_cache_code_path = repo_directory + "/app/ndnx_content_key_cache.py"
        ndnx_cache_app_asset = s3_assets.Asset(
            self, "ndnx_cache_asset", path=ndnx_cache_code_path
        )

        # create ec2 role for NDNx Cache
        ndnx_cache_ec2_role = iam.Role(
            self,
            "NDNxCacheRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
        )

        # attach policies for allowing usage of SSM profiles and access to the service code in S3
        ndnx_cache_ec2_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess")
        )
        ndnx_cache_ec2_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonSSMManagedInstanceCore"
            )
        )

        # allow ec2 role to get asset
        ndnx_cache_app_asset.grant_read(ndnx_cache_ec2_role)

        # User data script for deploying the code from S3 to the provisioned server
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            # Set env var for encrypted content key
            f"export ndnx_encrypted_content_key={ENCRYPTED_CONTENT_KEY}",
            "yum update -y",
            # Create a dir for the app
            "mkdir -p /opt/app",
            f"cd /opt/app",
            # Download the asset bundle from S3
            f"aws s3 cp {ndnx_cache_app_asset.s3_object_url} ndnx_content_key_cache.py",
            # Install dependencies
            "python3 -m pip install --upgrade pip",
            "pip3 install flask",
            # Start the app
            "python3 ndnx_content_key_cache.py",
        )

        # Server for ndnx cache
        ndnx_cache_server = ec2.Instance(
            self,
            "NDNxCache",
            instance_type=ec2.InstanceType("t4g.micro"),
            machine_image=ec2.MachineImage.latest_amazon_linux2(
                cpu_type=ec2.AmazonLinuxCpuType.ARM_64,
            ),
            vpc=vpc,
            security_group=self.ndnx_cache_sg,
            instance_name="NDNxCache",
            user_data=user_data,
            role=ndnx_cache_ec2_role,
        )
        # Save the public IP of the cache server to set in VPN service env variables
        cache_domain = ndnx_cache_server.instance_public_ip

        # Security Group for VPN server
        self.vpn_sg = ec2.SecurityGroup(
            self,
            "VPNServerSG",
            vpc=vpc,
            description="Security Group for VPN service",
            allow_all_outbound=True,
        )
        # For ease in cross-region requests and since these servers are short lived, full ingress is allowed.
        self.vpn_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(8000),
            "Allow requests over 8000 from anywhere",
        )

        # put service code in s3 for deployment
        vpn_service_code_path = repo_directory + "/app/vpn_service.py"

        vpn_service_app_asset = s3_assets.Asset(
            self, "vpn_service_asset", path=vpn_service_code_path
        )

        # create ec2 role for VPN Server
        vpn_service_ec2_role = iam.Role(
            self,
            "VPNServiceServerRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
        )
        # attach policies for allowing usage of SSM profiles and access to the service code in S3
        vpn_service_ec2_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess")
        )
        vpn_service_ec2_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonSSMManagedInstanceCore"
            )
        )

        # allow ec2 role to get asset
        vpn_service_app_asset.grant_read(vpn_service_ec2_role)

        # User data script for setting env vars and deploying the code from S3 to the provisioned server
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            # Set env variables
            f"export ndnx_qa_cdn_url={CDN_URL}",
            f"export ndnx_qa_key={QA_KEY}",
            f"export ndnx_content_key={CONTENT_KEY}",
            f"export ndnx_content_key_cache={cache_domain}",
            "yum update -y",
            # Create a dir for the app
            "mkdir -p /opt/app",
            f"cd /opt/app",
            # Download the asset bundle from S3
            f"aws s3 cp {vpn_service_app_asset.s3_object_url} vpn_service.py",
            # Install dependencies
            "python3 -m pip install --upgrade pip",
            "pip3 install cryptography flask redis requests==2.29.0",
            # Start the app
            "python3 vpn_service.py",
        )

        # Server for VPN service
        ec2.Instance(
            self,
            "VPNServer",
            instance_type=ec2.InstanceType("t4g.micro"),
            machine_image=ec2.MachineImage.latest_amazon_linux2(
                cpu_type=ec2.AmazonLinuxCpuType.ARM_64,
            ),
            vpc=vpc,
            security_group=self.vpn_sg,
            instance_name="VPNServer",
            user_data=user_data,
            role=vpn_service_ec2_role,
        )


# ----------------------------------------------------------------------
# User Device VPC Stack – holds all entrypoint resources
# ----------------------------------------------------------------------
class UserDeviceVPCStack(Stack):
    """
    A stack that creates:
      • a VPC (default 1 AZ, 2 subnets)
      • an Amazon Linux 2 t3.micro instance
      • a security group that allows SSH (22) from anywhere
    """

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # VPC for server
        vpc = ec2.Vpc(
            self,
            "UserDeviceVpc",
            max_azs=1,  # Only 1 AZ – keeps costs low
            nat_gateways=0,  # No NAT – instance can reach the internet via public IP
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="UserDeviceVPCPublicSubnet",
                    subnet_type=ec2.SubnetType.PUBLIC,
                ),
            ],
        )

        # Security Group for server
        self.user_device_sg = ec2.SecurityGroup(
            self,
            "UserDeviceSG",
            vpc=vpc,
            description="Security Group for User Device",
            allow_all_outbound=True,
        )
        # For ease in cross-region requests and since these servers are short lived, full ingress is allowed.
        self.user_device_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(8000),
            "Allow requests over 8000 from anywhere",
        )

        # put service code in s3 for deployment
        current_directory = os.getcwd()
        repo_directory = os.path.abspath(
            os.path.join(current_directory, os.path.pardir)
        )
        code_path = repo_directory + "/app/user_device.py"

        app_asset = s3_assets.Asset(self, "user_device_asset", path=code_path)

        # create ec2 role for User Device server
        ec2_role = iam.Role(
            self,
            "UserDeviceServerRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
        )
        # attach policies for allowing usage of SSM profiles and access to the service code in S3
        ec2_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess")
        )
        ec2_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonSSMManagedInstanceCore"
            )
        )

        # allow ec2 role to get asset
        app_asset.grant_read(ec2_role)

        # User data script for setting env vars and deploying the code from S3 to the provisioned server
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            # Set env variables
            f"export ndnx_asset_key={ASSET_KEY}",
            f"export ndnx_content_key={CONTENT_KEY}",
            f"export ndnx_qa_content_cache={NDNX_CONTENT_CACHE}",
            f"export ndnx_qa_cdn_url={CDN_URL}",
            f"export ndnx_qa_key={QA_KEY}",
            "yum update -y",
            # Create a dir for the app
            "mkdir -p /opt/app",
            f"cd /opt/app",
            # Download the asset bundle from S3
            f"aws s3 cp {app_asset.s3_object_url} user_device.py",
            # Install dependencies
            "python3 -m pip install --upgrade pip",
            "pip3 install cryptography flask requests==2.29.0",
            # Start the app
            "python3 user_device.py",
        )

        # Server for User Device service
        ec2.Instance(
            self,
            "UserDevice",
            instance_type=ec2.InstanceType("t4g.micro"),
            machine_image=ec2.MachineImage.latest_amazon_linux2(
                cpu_type=ec2.AmazonLinuxCpuType.ARM_64
            ),
            vpc=vpc,
            security_group=self.user_device_sg,
            instance_name="UserDevice",
            user_data=user_data,
            role=ec2_role,
        )


# ----------------------------------------------------------------------
# CDK App – instantiate stacks
# ----------------------------------------------------------------------
app = App()

# To emphasize the effect of geo-distribution, the stacks are deployed in different regions
# For the NDNx Research Project, this makes it easier to statistically prove the performance benefit
# with lesser trials which was important for cost saving concerns.
vpn_env = Environment(region="ap-northeast-2")
user_device_env = Environment(region="us-west-2")

vpn_server_stack = VpnServiceStack(app, "VpnServiceStack", env=vpn_env)
user_device_stack = UserDeviceVPCStack(
    app,
    "UserDeviceStack",
    env=user_device_env,
)

app.synth()
