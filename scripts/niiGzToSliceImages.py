import sys

CT_PATH_FILE = sys.argv[1]
CT_SLICES_DIR = sys.argv[2]

if not os.path.exists(CT_SLICES_DIR):
  os.mkdir(CT_SLICES_DIR)

nii_path = CT_PATH_FILE

nii_img = nib.load(nii_path)

nii_data = nii_img.get_fdata()

output_dir = CT_SLICES_DIR
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

for i in range(nii_data.shape[2]):
    plt.imshow(nii_data[:, :, i], cmap="gray")
    plt.axis("off")
    plt.savefig(os.path.join(output_dir, f"slice_{i}.png"), bbox_inches="tight", pad_inches=0)
    plt.clf()