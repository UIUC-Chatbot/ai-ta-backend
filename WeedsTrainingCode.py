import os
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms
from torch.utils.data import DataLoader, Dataset
from PIL import Image
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, ConfusionMatrixDisplay
from torch.optim.lr_scheduler import StepLR, ReduceLROnPlateau  # Added ReduceLROnPlateau scheduler
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import logging
from torchvision.transforms import RandomApply  # RandomApply for augmentations
from torch.optim import Adam  # Adam optimizer
from torchvision.models import vgg16, densenet121


# Setup logging
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(filename='/Users/kavinjindel2004/Desktop/model_training2222.log', level=logging.INFO, format=log_format)


logging.info("Stage 1")
class_labels = {
    "BedstrawWeeds": 0,
    "Field penny-cressWeeds": 1,
    "PlantainWeeds": 2,
    "BindweedWeeds": 3,
    "HenbitWeeds": 4,
    "PurslaneWeeds": 5,
    "BlackMedicWeeds": 6,
    "HorseweedWeeds": 7,
    "RagweedWeeds": 8,
    "ChickWeeds": 9,
    "KnotweedWeeds": 10,
    "Shepherd_sPurseWeeds": 11,
    "CloverWeeds": 12,
    "KochiaWeeds": 13,
    "SpeedwellWeeds": 14,
    "CrabgrassWeeds": 15,
    "LambsquartersWeeds": 16,
    "ThistleWeeds": 17,
    "CreepingCharlieWeeds": 18,
    "NutgrassWeeds": 19,
    "VelvetleafWeeds": 20,
    "CurlyDockWeeds": 21,
    "NutsedgeWeeds": 22,
    "WildVioletsWeeds": 23,
    "DandelionWeeds": 24,
    "PineappleweedWeeds": 25,
    "YellowWoodSorrelWeeds": 26
}


class EarlyStopping:
    def __init__(self, patience=20, path='checkpoint.pth', delta=0):
        self.patience = patience
        self.counter = 0
        self.best_score = None
        self.early_stop = False
        self.val_loss_min = np.Inf
        self.delta = delta
        self.path = path

    def __call__(self, val_loss, model):
        score = -val_loss
        if self.best_score is None:
            self.best_score = score
            self.save_checkpoint(val_loss, model)
        elif score < self.best_score + self.delta:
            self.counter += 1
            logging.info(f'EarlyStopping counter: {self.counter} out of {self.patience}')
            if self.counter >= self.patience:
                self.early_stop = True
        else:
            self.best_score = score
            self.save_checkpoint(val_loss, model)
            self.counter = 0

    def save_checkpoint(self, val_loss, model):
        torch.save(model.state_dict(), self.path)
        self.val_loss_min = val_loss

from PIL import ImageEnhance
logging.info("Stage 2")
class BinaryDataset(Dataset):
    def __init__(self, root_dir, transform=None):
        self.root_dir = root_dir
        self.transform = transform
        self.classes = list(class_labels.keys())
        self.img_list = []
        for class_name in self.classes:
            class_dir = os.path.join(self.root_dir, class_name)
            for filename in os.listdir(class_dir):
                if filename.endswith(".jpg") and not filename.startswith("._"):  
                    self.img_list.append((os.path.join(class_dir, filename), class_name))


    def __len__(self):
        return len(self.img_list)

    def __getitem__(self, idx):
        img_path, class_name = self.img_list[idx]
        img = Image.open(img_path).convert("RGB")

        if self.transform is not None:
            img = self.transform(img)
        label = torch.tensor(class_labels[class_name], dtype=torch.long)
        return img, label
logging.info("Stage 3")
# Path to your dataset
dataset_path = "/Users/kavinjindel2004/Downloads/DatasetSelfMade"
logging.info("Stage 4")

# Transformations
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    RandomApply([  # Randomly applies the list of transforms with a given probability
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(),  
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1, hue=0.1)
    ], p=0.5),  # 50% chance to apply these augmentations
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])  
])

logging.info("Stage 5")

# Creating the dataset
dataset = BinaryDataset(dataset_path, transform=transform)
logging.info("Stage 6")

# Define models to be used
model_names = ["resnet18"]
models = [models.resnet18]



# Create folder for saved models
if not os.path.exists('/Users/kavinjindel2004/Desktop/saved_models'):
    os.makedirs('/Users/kavinjindel2004/Desktop/saved_models')

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")  

batch_size = 16
num_epochs = 60
criterion = nn.CrossEntropyLoss()

# Preparing for k-Fold Cross Validation
k_folds = 2
kfold = StratifiedKFold(n_splits=k_folds, shuffle=True)
logging.info("Stage 7")

# Extract labels for stratified splitting
labels = [label for _, label in dataset]

# Dictionary to store accuracy for each model
model_acc_dict = {model_name: [] for model_name in model_names}
model_f1_dict = {model_name: [] for model_name in model_names}
logging.info("Stage 8")

# K-Fold Cross Validation
for fold, (train_ids, val_test_ids) in enumerate(kfold.split(np.zeros(len(dataset)), labels)):
    # Split validation and test sets
    half_split = int(0.5 * len(val_test_ids))
    val_ids = val_test_ids[:half_split]
    test_ids = val_test_ids[half_split:]

    # logging.info
    logging.info(f'FOLD {fold}')
    logging.info('--------------------------------')

    # Sample elements randomly from a given list of ids, no replacement.
    train_subsampler = torch.utils.data.SubsetRandomSampler(train_ids)
    val_subsampler = torch.utils.data.SubsetRandomSampler(val_ids)
    test_subsampler = torch.utils.data.SubsetRandomSampler(test_ids)

    # Define data loaders for training, validation and testing data in this fold
    trainloader = torch.utils.data.DataLoader(
        dataset, 
        batch_size=batch_size, sampler=train_subsampler)
    valloader = torch.utils.data.DataLoader(
        dataset, 
        batch_size=batch_size, sampler=val_subsampler)
    testloader = torch.utils.data.DataLoader(
        dataset,
        batch_size=batch_size, sampler=test_subsampler)

    # Init the neural network
    for model_name, model_func in zip(model_names, models):
        model = model_func(pretrained=True)
        if model_name == "alexnet":
            num_ftrs = model.classifier[6].in_features
            model.classifier[6] = nn.Linear(num_ftrs, len(class_labels))
        elif model_name == "efficientnet":
            num_ftrs = model._fc.in_features
            model._fc = nn.Linear(num_ftrs, len(class_labels))
        elif model_name == "densenet121":
            num_ftrs = model.classifier.in_features
            model.classifier = nn.Linear(num_ftrs, len(class_labels))
        else:
            num_ftrs = model.fc.in_features
            model.fc = nn.Linear(num_ftrs, len(class_labels))



        model = model.to(device)
        optimizer = Adam(model.parameters(), lr=0.001)  # Change SGD to Adam, often performs better
        scheduler = ReduceLROnPlateau(optimizer, mode='min', factor=0.1, patience=10, verbose=True)  # Change to ReduceLROnPlateau which is often better for CNNs

        early_stopping = EarlyStopping(patience=20, path=f'/Users/kavinjindel2004/Desktop/saved_models/{model_name}_checkpoint_fold_{fold}.pth')

        # Training Loop
        for epoch in range(0, num_epochs):
            logging.info(f'Starting epoch {epoch+1} for {model_name}')
            current_loss = 0.0
            model.train()
            for i, (inputs, labels) in enumerate(trainloader, 0):
                inputs = inputs.to(device)
                labels = labels.to(device)
                optimizer.zero_grad()
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()
                current_loss += loss.item()
                if i % 10 == 9:
                    logging.info('Loss after mini-batch %5d: %.3f' % (i + 1, current_loss / 10))
                    current_loss = 0.0
            logging.info('Training process has finished for epoch.')
            # Validate the model
            model.eval()
            val_correct, val_total = 0, 0
            val_labels = []
            val_predictions = []
            with torch.no_grad():
                for i, (inputs, labels) in enumerate(valloader, 0):
                    # Put inputs and labels on GPU
                    inputs = inputs.to(device)
                    labels = labels.to(device)

                    # Generate outputs
                    outputs = model(inputs)

                    # Set total and correct
                    _, predicted = torch.max(outputs.data, 1)
                    val_total += labels.size(0)
                    val_correct += (predicted == labels).sum().item()

                    # Append batch prediction results
                    val_labels += labels.tolist()
                    val_predictions += predicted.tolist()

                # Compute loss and accuracy
                val_loss = criterion(outputs, labels)
                val_accuracy = val_correct / val_total

                logging.info(f'Validation Loss: {val_loss:.4f}, Accuracy: {val_accuracy:.4f}')

            # Adjust the learning rate
            scheduler.step(val_loss)

            # Early Stopping 
            early_stopping(val_loss, model)
            if early_stopping.early_stop:
                logging.info("Early stopping")
                # load the last checkpoint with the best model
                model.load_state_dict(torch.load(f'/Users/kavinjindel2004/Desktop/saved_models/{model_name}_checkpoint_fold_{fold}.pth'))

                break

                # Evaluation for this fold
        correct, total = 0, 0
        all_labels = []
        all_predictions = []
        model.eval()  # set the model to evaluation mode
        with torch.no_grad():

            # Iterate over the test data and generate predictions
            for i, (inputs, labels) in enumerate(testloader, 0):

                # Put inputs and labels on GPU
                inputs = inputs.to(device)
                labels = labels.to(device)

                # Generate outputs
                outputs = model(inputs)

                # Set total and correct
                _, predicted = torch.max(outputs.data, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()

                # Append batch prediction results
                all_labels += labels.tolist()
                all_predictions += predicted.tolist()

        # logging.info accuracy
        accuracy = correct / total
        model_acc_dict[model_name].append(accuracy)
        logging.info('Accuracy for fold %d: %.2f %%' % (fold, accuracy*100))

        # Compute precision, recall, confusion matrix and logging.info
        precision = precision_score(all_labels, all_predictions, average='weighted')
        recall = recall_score(all_labels, all_predictions, average='weighted')
        conf_matrix = confusion_matrix(all_labels, all_predictions)

        logging.info('Precision for fold %d: %.2f' % (fold, precision))
        logging.info('Recall for fold %d: %.2f' % (fold, recall))
        logging.info('Confusion Matrix for fold %d: \n%s' % (fold, str(conf_matrix)))


        # Compute f1_score and logging.info
        f1 = f1_score(all_labels, all_predictions, average='weighted')
        model_f1_dict[model_name].append(f1)
        logging.info('F1 Score for fold %d: %.2f' % (fold, f1))


    logging.info('--------------------------------')
    logging.info('--------------------------------')

# Plotting the accuracies and F1 scores for each model across folds
plt.figure(figsize=(12,6))
for model_name, acc_list in model_acc_dict.items():
    plt.plot(range(1, k_folds + 1), acc_list, marker='o', markersize=5, label=model_name)
plt.xlabel('Fold Number')
plt.ylabel('Accuracy')
plt.title('Comparison of Model Accuracies Across Folds')
plt.legend()
plt.grid()
plt.savefig('/Users/kavinjindel2004/Desktop/model_accuracies.png')
plt.show()

plt.figure(figsize=(12,6))
for model_name, f1_list in model_f1_dict.items():
    plt.plot(range(1, k_folds + 1), f1_list, marker='o', markersize=5, label=model_name)
plt.xlabel('Fold Number')
plt.ylabel('F1 Score')
plt.title('Comparison of Model F1 Scores Across Folds')
plt.legend()
plt.grid()
plt.savefig('/Users/kavinjindel2004/Desktop/model_F1scores.png')
plt.show()

logging.info('Training, Validation, and Testing finished')

def predict_image(image_path, model, transform, device):
    
    model.eval()
    
    if isinstance(image_path, str):
        image_paths = [image_path]
    else:
        image_paths = image_path
    
    predictions = []
    for path in image_paths:
        img = Image.open(path).convert("RGB")
        img = transform(img)
        img = img.unsqueeze(0).to(device)
        
        with torch.no_grad():
            outputs = model(img)
            _, predicted = torch.max(outputs, 1)
            prediction_label = list(class_labels.keys())[predicted.item()]
            predictions.append(prediction_label)
    
    return predictions

if __name__ == "__main__":

    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)  
    
    image_path = "/path/to/your/image.jpg"  
    
    prediction = predict_image(image_path, model, transform, device)
    print("Predicted class:", prediction)
