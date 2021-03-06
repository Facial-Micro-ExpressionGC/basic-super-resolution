from __future__ import print_function

from math import log10

import torch
import torch.backends.cudnn as cudnn

from CARN.model import Net
from progress_bar import progress_bar

from Trainer import Trainer

class CARNTrainer(Trainer):
    def __init__(self, config, training_loader, testing_loader):
        super(CARNTrainer, self).__init__()
        self.config = config
        self.CUDA = torch.cuda.is_available()
        self.device = torch.device('cuda' if self.CUDA else 'cpu')
        self.model = None
        self.lr = config.lr
        self.nEpochs = config.nEpochs
        self.criterion = None
        self.optimizer = None
        self.scheduler = None
        self.seed = config.seed
        self.upscale_factor = config.upscale_factor
        self.training_loader = training_loader
        self.testing_loader = testing_loader

    def build_model(self):
        self.model = Net(scale=self.upscale_factor).to(self.device)
        # self.model.weight_init(mean=0.0, std=0.01)
        self.criterion = torch.nn.MSELoss()
        torch.manual_seed(self.seed)

        if self.CUDA:
            torch.cuda.manual_seed(self.seed)
            cudnn.benchmark = True
            self.criterion.cuda()

        self.set_optimizer() #==> Add

    def train(self):
        self.model.train()
        train_loss = 0
        for batch_num, (data, target) in enumerate(self.training_loader):
            data, target = data.to(self.device), target.to(self.device)
            self.optimizer.zero_grad()
            loss = self.criterion(self.model(data, self.config.upscale_factor), target)
            train_loss += loss.item()
            loss.backward()
            self.optimizer.step()
            total_time = progress_bar(batch_num, len(self.training_loader), 'Loss: %.4f' % (train_loss / (batch_num + 1)), verbos=True)

        avg_loss = train_loss / len(self.training_loader)
        return [avg_loss, total_time]

    def test(self):
        self.model.eval()
        avg_psnr = 0

        with torch.no_grad():
            for batch_num, (data, target) in enumerate(self.testing_loader):
                data, target = data.to(self.device), target.to(self.device)
                prediction = self.model(data, self.config.upscale_factor)
                mse = self.criterion(prediction, target)
                psnr = 10 * log10(1 / mse.item())
                avg_psnr += psnr
                total_time = progress_bar(batch_num, len(self.testing_loader), 'PSNR: %.4f' % (avg_psnr / (batch_num + 1)))

        avg_psnr = avg_psnr / len(self.testing_loader)
        return [avg_psnr, total_time]

    def run(self):
        self.build_model()
        for epoch in range(1, self.nEpochs + 1):
            print("\n===> Epoch {} starts:".format(epoch))
            avg_loss = self.train()
            avg_psnr = self.test()
            self.scheduler.step(epoch)
            self.save_model(epoch=epoch, avg_error=avg_loss, avg_psnr=avg_psnr)
