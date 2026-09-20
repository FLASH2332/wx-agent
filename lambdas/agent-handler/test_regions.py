import boto3

regions_and_profiles = [
    ("eu-west-1", "eu.amazon.nova-lite-v1:0"),
    ("eu-central-1", "eu.amazon.nova-lite-v1:0"),
    ("ap-southeast-1", "ap.amazon.nova-lite-v1:0"),
]

for region, profile in regions_and_profiles:
    try:
        client = boto3.client("bedrock-runtime", region_name=region)
        response = client.converse_stream(
            modelId=profile,
            messages=[{"role": "user", "content": [{"text": "hi"}]}],
        )
        for event in response["stream"]:
            if "contentBlockDelta" in event:
                print(f"{region} / {profile}: OK")
                break
    except Exception as e:
        print(f"{region} / {profile}: FAILED — {e}")