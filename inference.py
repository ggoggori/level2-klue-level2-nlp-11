from transformers import AutoTokenizer, AutoConfig, AutoModelForSequenceClassification, Trainer, TrainingArguments
from torch.utils.data import DataLoader
from load_data import *
import pandas as pd
import torch
import torch.nn.functional as F
import yaml
import json
import pickle as pickle
import numpy as np
from tqdm import tqdm

def inference(model, tokenized_sent, device):
  """
    test dataset을 DataLoader로 만들어 준 후,
    batch_size로 나눠 model이 예측 합니다.
  """
  dataloader = DataLoader(tokenized_sent, batch_size=16, shuffle=False, collate_fn=collate_fn)
  model.eval()
  output_pred = []
  output_prob = []
  for i, data in enumerate(tqdm(dataloader)):
    with torch.no_grad():
      outputs = model(
          input_ids=data['input_ids'].to(device),
          attention_mask=data['attention_mask'].to(device),
          token_type_ids=data['token_type_ids'].to(device)
          )
    logits = outputs[0]
    prob = F.softmax(logits, dim=-1).detach().cpu().numpy()
    logits = logits.detach().cpu().numpy()
    result = np.argmax(logits, axis=-1)

    output_pred.append(result)
    output_prob.append(prob)
  
  return np.concatenate(output_pred).tolist(), np.concatenate(output_prob, axis=0).tolist()

def num_to_label(label):
  """
    숫자로 되어 있던 class를 원본 문자열 라벨로 변환 합니다.
  """
  origin_label = []
  with open('dict_num_to_label.pkl', 'rb') as f:
    dict_num_to_label = pickle.load(f)
  for v in label:
    origin_label.append(dict_num_to_label[v])
  
  return origin_label

def load_test_dataset(dataset_dir, tokenizer, input_type):
  """
    test dataset을 불러온 후,
    tokenizing 합니다.
  """
  test_dataset = load_data(dataset_dir)
  test_label = list(map(int,test_dataset['label'].values))
  # tokenizing dataset
  tokenized_test = tokenized_dataset(test_dataset, tokenizer, input_type)
  return test_dataset['id'], tokenized_test, test_label

def main():
  """
    주어진 dataset csv 파일과 같은 형태일 경우 inference 가능한 코드입니다.
  """
  config = yaml.load(open("/opt/ml/code/best_model/config.yaml", "r"), Loader=yaml.FullLoader) # load config
  device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu') # load device
  
  # load tokenizer
  Tokenizer_NAME = config['model']['name']
  tokenizer = AutoTokenizer.from_pretrained(Tokenizer_NAME)

  ## load my model
  MODEL_NAME = config["inference"]["model_dir"] # model dir.
  model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
  model.parameters
  model.to(device)

  ## load test datset
  test_dataset_dir = config["dir"]["test"]
  test_id, test_dataset, test_label = load_test_dataset(test_dataset_dir, tokenizer, config['input_type'])
  Re_test_dataset = RE_Dataset(test_dataset ,test_label)

  ## predict answer
  pred_answer, output_prob = inference(model, Re_test_dataset, device) # model에서 class 추론
  pred_answer = num_to_label(pred_answer) # 숫자로 된 class를 원래 문자열 라벨로 변환.
  
  ## make csv file with predicted answer
  output = pd.DataFrame({'id':test_id,'pred_label':pred_answer,'probs':output_prob,})

  output.to_csv(config["dir"]["output"], index=False) # 최종적으로 완성된 예측한 라벨 csv 파일 형태로 저장.
  print('---- Finish! ----')

if __name__ == '__main__':
  main()
  
