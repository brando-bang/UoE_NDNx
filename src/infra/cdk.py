import os

from aws_cdk import (
    App,
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_s3_assets as s3_assets,
)
from constructs import Construct


# ----------------------------------------------------------------------
# VPN VPC Stack – holds all VPN resources
# ----------------------------------------------------------------------
class VpnVpcStack(Stack):
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
            "VpnVpc",
            max_azs=1,               # Only 1 AZ – keeps costs low
            nat_gateways=0,          # No NAT – instance can reach the internet via public IP
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="PublicSubnet",
                    subnet_type=ec2.SubnetType.PUBLIC,
                ),
            ],
        )

        # Security Group for server
        sg = ec2.SecurityGroup(
            self,
            "VpnServerSG",
            vpc=vpc,
            description="Allow SSH inbound",
            allow_all_outbound=True,
        )
        sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(22),
            "Allow SSH from anywhere",
        )
        sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(8000),
            "Allow requests over 8000 from anywhere",
        )

        # put service code in s3 for deployment
        current_directory = os.getcwd()
        repo_directory = os.path.abspath(os.path.join(current_directory, os.path.pardir))
        code_path = repo_directory + "/app/vpn_service.py"

        app_asset = s3_assets.Asset(self, "AppAsset",
                                   path=code_path)

        # create ec2 role
        ec2_role = iam.Role(
            self,
            "WebServerInstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
        )
        # attach the S3 Policy
        ec2_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonS3FullAccess"
            )
        )

        # allow ec2 role to get asset
        app_asset.grant_read(ec2_role)

        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "yum update -y",

            # Create a dir for the app
            "mkdir -p /opt/app",
            f"cd /opt/app",

            # Download the asset bundle from S3
            f"aws s3 cp {app_asset.s3_object_url} vpn_service.py",

            # Install dependencies
            "python3 -m pip install --upgrade pip",
            "pip3 install flask",

            # Start the app
            "python3 vpn_service.py"
        )

        # Server for VPN service
        ec2.Instance(
            self,
            "VPNServer",
            instance_type=ec2.InstanceType("t4g.micro"),
            machine_image=ec2.MachineImage.latest_amazon_linux(
                cpu_type=ec2.AmazonLinuxCpuType.ARM_64,
                generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
            ),
            vpc=vpc,
            security_group=sg,
            instance_name="VPNServer",
            user_data=user_data,
            role=ec2_role
        )

# ----------------------------------------------------------------------
# CDK App – instantiate both stacks
# ----------------------------------------------------------------------
app = App()

vpn_stack = VpnVpcStack(app, "VpnVpcStack")

app.synth()