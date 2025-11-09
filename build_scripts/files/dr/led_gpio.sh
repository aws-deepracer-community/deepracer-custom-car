#!/bin/sh

NAME=$(basename "$0")

SYSPATH=/sys/class/gpio

usage() {
  echo "Usage:
  $NAME <command> [options]

Options:
  -h, --help    Show usage

Commands:
  export [on/off]      Export GPIOs
  unexport             Unexport GPIOs

Example:
  led_gpio.sh export on   //export GPIO and turn on all LED
  led_gpio.sh export off  //export GPIO and turn off all LED

Sel LED color:
  sudo echo 1 >/sys/class/gpio/gpio526/value    //WLN_LEDEN_R
  sudo echo 1 >/sys/class/gpio/gpio525/value    //WLN_LEDEN_G
  sudo echo 1 >/sys/class/gpio/gpio515/value    //WLN_LEDEN_B

  sudo echo 1 >/sys/class/gpio/gpio524/value    //CAM_LEDEN_R
  sudo echo 1 >/sys/class/gpio/gpio523/value    //CAM_LEDEN_G
  sudo echo 1 >/sys/class/gpio/gpio521/value    //CAM_LEDEN_B

  sudo echo 1 >/sys/class/gpio/gpio528/value    //PWR_LEDEN_R
  sudo echo 1 >/sys/class/gpio/gpio535/value    //PWR_LEDEN_G
  sudo echo 1 >/sys/class/gpio/gpio536/value    //PWR_LEDEN_B

"
}

export_gpio() {
  pin_num=$1
  pin_dir=$2
  pin_val=$3
  pin_edge=$4
  gpio_path="$SYSPATH/gpio$pin_num"

  if [ ! -d $gpio_path ]; then
    echo $pin_num > $SYSPATH/export
  fi
  if [ "$pin_dir" ]; then
    echo $pin_dir > $gpio_path/direction
  fi
  if [ "$pin_dir" = "out" ]; then
    if [ "$pin_val" ]; then
      echo $pin_val > $gpio_path/value
    fi
  fi
  if [ "$pin_edge" ]; then
    echo $pin_edge > $gpio_path/edge
  fi
  chmod 666 $gpio_path/value
}

export_gpios() {
  if [ $1 = "on" ]; then
	#WLN_LEDEN_B
	export_gpio 515 out 1 
	#WLN_LEDEN_G
	export_gpio 525 out 1
	#WLN_LEDEN_R
	export_gpio 526 out 1  

	#CAM_LEDEN_B
	export_gpio 521 out 1  
	#CAM_LEDEN_G
	export_gpio 523 out 1 
	#CAM_LEDEN_R
	export_gpio 524 out 1

	#PWR_LEDEN_R
	export_gpio 528 out 1
	#PWR_LEDEN_G
	export_gpio 535 out 1   
	#PWR_LEDEN_B
	export_gpio 536 out 1  
   else
	#WLN_LEDEN_B
	export_gpio 515 out 0
	#WLN_LEDEN_G
	export_gpio 525 out 0
	#WLN_LEDEN_R
	export_gpio 526 out 0  

	#CAM_LEDEN_B
	export_gpio 521 out 0  
	#CAM_LEDEN_G
	export_gpio 523 out 0 
	#CAM_LEDEN_R
	export_gpio 524 out 0

	#PWR_LEDEN_R
	export_gpio 528 out 0
	#PWR_LEDEN_G
	export_gpio 535 out 0   
	#PWR_LEDEN_B
	export_gpio 536 out 0  

   fi
	

}

unexport_gpio() {
  gpio_num=$1
  gpio="$SYSPATH/gpio$gpio_num"

  if [ -d $gpio ]; then
     echo $gpio_num > $SYSPATH/unexport
  fi
}

unexport_gpios() {
   unexport_gpio 515
   unexport_gpio 525
   unexport_gpio 526

   unexport_gpio 521
   unexport_gpio 523
   unexport_gpio 524

   unexport_gpio 528
   unexport_gpio 535
   unexport_gpio 536
}

main() {
  case "$1" in
  -h|--help)
    usage
    exit
    ;;
  export)
    if [ ! -n "$2" ]; then
        usage
        exit 1
    fi
    cmd="export_gpios $2"
    ;;
  unexport)
    cmd="unexport_gpios"
    ;;
  *)
    usage >&2
    exit 1
    ;;
  esac

  $cmd
}

main "$@"
