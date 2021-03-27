import os
import PIL
import torch
import numpy as np
import pandas as pd
from PIL import Image
from torch.utils.data import Dataset, DataLoader
from torchvision.transforms import Resize, Normalize, ToTensor, Compose


class TrainTestDataset(Dataset):

    def __init__(
        self,
        data_path: str,
        image_dir: str,
        formulas_path: str,
        vocab_path: str,
        transform: None
    ):
        super().__init__()

        # Loading formulas
        with open(formulas_path, 'r') as f:
            strs = f.readlines()
        data = {'tokens': [np.array(s.split()) for s in strs]}
        self.formulas = pd.DataFrame(data)

        # Loading data (image and formula index)
        with open(data_path, 'r') as f:
            strs = f.readlines()
        strs = [s.split() for s in strs]
        data = np.array(list(zip(*strs))).T
        self.data = pd.DataFrame(data, columns=['image', 'idx'])
        self.data['idx'] = self.data['idx'].astype(int)

        # Loading LaTeX vocabulary
        with open(vocab_path, 'r') as f:
            strs = f.readlines()
        self.vocab = {s.strip(): i for i, s in enumerate(strs)}
        self.image_dir = image_dir
        self.transform = transform

    def __len__(self):
        return self.data.shape[0]

    def __getitem__(self, index):
        # Getting data
        item = self.data.iloc[index]
        formula = self.formulas.iloc[item.idx]
        im_path = os.path.join(self.image_dir, item.image)
        image = Image.open(im_path).convert('L')
        seq_len = len(formula)

        # Downsampling and transforming image
        image = self._downsample_image(image)
        if self.transform:
            image = self.transform(image)

        tokens = self._encode_tokens(formula)

        return image, tokens, seq_len

    def _encode_tokens(self, formula: list):
        """
        Encode sequence of tokens in formula.
        Returns torch.tensor of size (formula_len, vocab_len)
        """
        def encode(token):
            return self.vocab(token, self.vocab['UNKNOWN'])
        sequence = torch.zeros(len(formula), len(self.vocab))
        tokens_idx = list(map(encode, formula))
        sequence[np.arange(len(formula)), tokens_idx] = 1.0

        return sequence

    def _downsample_image(self, image: Image.Image) -> Image.Image:
        """
        Downsample given image by random ratio in interval [1, 1.5].
        Returns downsampled image
        """
        ratio = (np.random.randn() / 2) + 1
        old_size = image.size
        new_size = (int(old_size[0] / ratio), int(old_size[1] / ratio))
        image = image.resize(new_size, PIL.Image.LANCZOS)

        return image


def collate(batch, device):
    images, tokens, seq_len = zip(*batch)
    max_len = np.max(seq_len)
    tokens = [torch.cat((t, torch.zeros(max_len - t.shape[0], t.shape[1])))
              for t in tokens]
    batch = {
        'images': torch.tensor(images).to(device),
        'tokens': torch.tensor(tokens).to(device),
        'len': seq_len
    }

    return batch


def get_dataloader(
    data_path: str,
    image_dir: str,
    formulas_path: str,
    vocab_path: str,
    device: str,
    shuffle: bool
) -> DataLoader:

    transformer = Compose(
        Resize((1024, 1024)),
        ToTensor(),
        Normalize((0.5), (1))
    )

    dataset = TrainTestDataset(data_path, image_dir, formulas_path, vocab_path)
    dataloader = DataLoader(dataset, batch_size=8, shuffle=shuffle,
                            collate_fn=lambda x: collate(x, device))
    return dataloader