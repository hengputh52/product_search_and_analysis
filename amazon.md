1. Amazon Berkeley Objects (ABO) ⭐ Best overall
147,000+ real Amazon products with high-res images
Multiple images per product (front, back, 360°)
Rich metadata: title, brand, description, category, color, dimensions, price
Filter by product_type to get electronics (HEADPHONES, LAPTOP, CELLULAR_PHONE, TELEVISION, TABLET, CAMERA, SPEAKERS)
Images hosted on AWS S3 — direct URLs
License: CC BY-NC 4.0 (academic use allowed)
No account needed
bash
# Download metadata + images (no AWS account)
aws s3 cp --no-sign-request s3://amazon-berkeley-objects/listings/metadata/ ./data/listings --recursive
aws s3 cp --no-sign-request s3://amazon-berkeley-objects/images/metadata/ ./data/images --recursive

# Images are at: s3://amazon-berkeley-objects/images/original/<path>

🔗 https://registry.opendata.aws/amazon-berkeley-objects/


https://amazon-berkeley-objects.s3.amazonaws.com/listings/metadata/listings_{0-9,a-f}.json.gz   (16 files, ~87 MB)

https://amazon-berkeley-objects.s3.amazonaws.com/images/metadata/images.csv.gz                  (image_id → path, ~6 MB)

https://amazon-berkeley-objects.s3.amazonaws.com/images/small/<path>                            (resized image URL)
