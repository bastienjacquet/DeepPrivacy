from optparse import OptionParser
from wordgenerator import generate_random_word
import os
import math
import json
import torch
DEFAULT_NUM_EPOCHS = 500
DEFAULT_BATCH_SIZE = "256,256,256,128,72,24,8,7,7" # V100-32GB settings
DEFAULT_N_CRITIC = 1
DEFAULT_LEARNING_RATE = 0.00125
DEFAULT_IMSIZE = 4
DEFAULT_MAX_IMSIZE = 128
DEFAULT_START_CHANNEL_SIZE = 256
DEFALUT_DATASET = "yfcc100m"
DEFAULT_TRANSITION_ITERS = 12e5
DEFAULT_GENERATOR_RUNNING_AVERAGE_DECAY = 0.999
DEFAULT_POSE_SIZE = 14
OPTIONS_DIR = "options"
DEFAULT_OPT_LEVEL = "O1"
DEFAULT_DISCRIMINATOR_MODEL = "normal"
os.makedirs(OPTIONS_DIR, exist_ok=True)


def validate_start_channel_size(max_imsize, start_channel_size):
    # Assert start channel size is valid with the max imsize
    # Number of times to double
    n_image_double =  math.log(max_imsize, 2) - 2 # starts at 4
    n_channel_halving = math.log(start_channel_size, 2) + 2
    assert n_image_double < n_channel_halving


def print_options(dic):
    #dic = vars(options)
    if "local_rank" in dic and dic["local_rank"] != 0:
        return
    print("="*80)
    print("OPTIONS USED:")
    banned_keys = ["G", "D", "g_optimizer", "d_optimizer", "z_sample", "running_average_generator"]
    for (key, item) in dic.items():
        if key in banned_keys:
            continue
        print("{:<16} {}".format(key, item))
    print("="*80)


def check_distributed(options):
    options.world_size = 1
    if "WORLD_SIZE" in os.environ:
        options.distributed = int(os.environ["WORLD_SIZE"]) > 1
    else:
        options.distributed = False
    if options.distributed:
        print("Enabling distributed training. Number of GPUs:", os.environ["WORLD_SIZE"])
        torch.cuda.set_device(options.local_rank)
        torch.distributed.init_process_group(backend="nccl", init_method="env://")
        options.world_size = torch.distributed.get_world_size()


def load_options():
    parser = OptionParser()
    parser.add_option("-b", "--batch-size", dest="batch_size",
                      help="Set batch size for training. Format: {batch-size 4x4},{bs, 8x8},{16x16},..{1024x1024}",
                      default=DEFAULT_BATCH_SIZE)
    parser.add_option("-c", "--n-critic", dest="n_critic",
                      help="Set number of critic(discriminator) batch step per generator step",
                      default=DEFAULT_N_CRITIC, type=int)
    parser.add_option("-l", "--learning-rate", dest="learning_rate",
                      help="Set learning rate",
                      default=DEFAULT_LEARNING_RATE, type=float)
    parser.add_option("-p", "--pose-size", dest="pose_size",
                      help="Set dimension of pose information.",
                      default=DEFAULT_POSE_SIZE, type=int)
    parser.add_option("-e", "--num-epochs", dest="num_epochs",
                      help="Set number of epochs",
                      default=DEFAULT_NUM_EPOCHS, type=int)
    parser.add_option("--name", "--model-name", dest="model_name",
                      help="Set the name of the model",
                      default=generate_random_word(), type=str)
    parser.add_option("--imsize", dest="imsize",
                      help="Set the image size for discriminator and generator",
                      default=DEFAULT_IMSIZE, type=int)
    parser.add_option("--max-imsize", dest="max_imsize",
                      help="Set the final image size for the discriminator and generator",
                      default=DEFAULT_MAX_IMSIZE, type=int)
    parser.add_option("--start-channel-size", dest="start_channel_size",
                      help="Set the channel start size for Discriminator and Generator",
                      default=DEFAULT_START_CHANNEL_SIZE, type=int)
    parser.add_option("--dataset", dest="dataset",
                      help="Set the dataset to load",
                      default=DEFALUT_DATASET)
    parser.add_option("--transition-iters", dest="transition_iters",
                      help="Set the number of images to show each transition phase",
                      default=DEFAULT_TRANSITION_ITERS, type=int)
    parser.add_option("--running-average-generator-decay", dest="running_average_generator_decay",
                      help="Set the decay rate for the running average of the generator",
                      default=DEFAULT_GENERATOR_RUNNING_AVERAGE_DECAY,
                      type=float)
    parser.add_option("--opt-level", dest="opt_level",
                      help="Set the optimization level for APEX",
                      default=DEFAULT_OPT_LEVEL,
                      type=str)
    parser.add_option("--discriminator-model", dest="discriminator_model",
                       help="Set the default discriminator architecture",
                       default=DEFAULT_DISCRIMINATOR_MODEL)
    parser.add_option("--local_rank", default=0, type=int,)

    options, _ = parser.parse_args()
    
    validate_start_channel_size(options.max_imsize, options.start_channel_size)

    options.checkpoint_dir = os.path.join("checkpoints", options.model_name)
    options.generated_data_dir = os.path.join("generated_data", options.model_name)
    options.summaries_dir = os.path.join("summaries", options.model_name)
    os.makedirs(options.checkpoint_dir, exist_ok=True)
    os.makedirs(options.generated_data_dir, exist_ok=True)

    imsizes = [4*2**i for i in range(0, 9)]
    batch_sizes = options.batch_size.split(",")
    scheduled_batch_size = {imsize: int(batch_sizes[i]) for i, imsize in enumerate(imsizes)}

    options.batch_size = scheduled_batch_size
    assert options.opt_level in ["O1","O0"], "Optimization level not correct. It was: {}".format(options.opt_level)

    print_options(vars(options))
    check_distributed(options)
    return options


if __name__ == '__main__':
    load_options()
