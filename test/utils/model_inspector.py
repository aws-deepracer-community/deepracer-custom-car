#!/usr/bin/env python3

"""
TensorFlow Model Inspector Utility

A simple utility to inspect TensorFlow model files (.pb) and display their structure,
including inputs, outputs, and operations. This helps with debugging model conversion issues.

Usage:
    python3 model_inspector.py /path/to/model.pb
"""

import os
import sys
import argparse


def inspect_tensorflow_model(model_path, show_all_ops=False, filter_ops=None):
    """
    Inspect a TensorFlow model file and display its structure.
    
    Args:
        model_path (str): Path to the TensorFlow model (.pb file)
        show_all_ops (bool): Whether to show all operations (can be very long)
        filter_ops (str): Filter operations by name pattern
    
    Returns:
        dict: Inspection results
    """
    try:
        # Try to use TensorFlow if available
        try:
            import tensorflow.compat.v1 as tf
            tf.disable_v2_behavior()
            use_tf = True
        except ImportError:
            print("⚠️  TensorFlow not available, using basic inspection")
            use_tf = False
        
        if use_tf:
            return _inspect_with_tensorflow(model_path, show_all_ops, filter_ops)
        else:
            return _inspect_basic(model_path)
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'model_path': model_path
        }


def _inspect_with_tensorflow(model_path, show_all_ops=False, filter_ops=None):
    """Inspect model using TensorFlow"""
    import tensorflow.compat.v1 as tf
    
    # Load the model
    with tf.gfile.GFile(model_path, 'rb') as f:
        graph_def = tf.GraphDef()
        graph_def.ParseFromString(f.read())
    
    # Create session and import graph
    with tf.Session() as sess:
        tf.import_graph_def(graph_def, name='')
        
        # Get all operations
        ops = sess.graph.get_operations()
        
        # Analyze operations
        inputs = []
        outputs = []
        all_ops = []
        op_types = {}
        
        for op in ops:
            # Count operation types
            op_types[op.type] = op_types.get(op.type, 0) + 1
            
            # Store operation info
            op_info = {
                'name': op.name,
                'type': op.type,
                'input_count': len(op.inputs),
                'output_count': len(op.outputs),
                'input_names': [inp.name for inp in op.inputs],
                'output_names': [out.name for out in op.outputs]
            }
            
            # Get shapes if possible
            try:
                if op.outputs:
                    shapes = []
                    dtypes = []
                    for out in op.outputs:
                        try:
                            shapes.append(out.shape.as_list())
                            dtypes.append(out.dtype.name)
                        except:
                            shapes.append("Unknown")
                            dtypes.append("Unknown")
                    op_info['output_shapes'] = shapes
                    op_info['output_dtypes'] = dtypes
            except:
                pass
            
            all_ops.append(op_info)
            
            # Look for placeholder operations (inputs)
            if op.type == 'Placeholder':
                try:
                    shape = op.outputs[0].shape.as_list() if op.outputs else "Unknown"
                    dtype = op.outputs[0].dtype.name if op.outputs else "Unknown"
                    inputs.append({
                        'name': op.name,
                        'shape': shape,
                        'dtype': dtype,
                        'output_tensor': op.outputs[0].name if op.outputs else None
                    })
                except:
                    inputs.append({
                        'name': op.name,
                        'shape': "Unknown",
                        'dtype': "Unknown",
                        'output_tensor': None
                    })
            
            # Look for potential outputs (operations with no consumers or specific patterns)
            is_potential_output = False
            
            # Check if it's a final operation (no consumers)
            has_consumers = any(consumer for out in op.outputs for consumer in out.consumers())
            if not has_consumers and op.outputs:
                is_potential_output = True
            
            # Check for specific output patterns
            output_keywords = ['policy', 'output', 'prediction', 'action', 'logits', 'value']
            if any(keyword in op.name.lower() for keyword in output_keywords):
                is_potential_output = True
            
            if is_potential_output:
                try:
                    shape = op.outputs[0].shape.as_list() if op.outputs else "Unknown"
                    dtype = op.outputs[0].dtype.name if op.outputs else "Unknown"
                    outputs.append({
                        'name': op.name,
                        'type': op.type,
                        'shape': shape,
                        'dtype': dtype,
                        'output_tensor': op.outputs[0].name if op.outputs else None,
                        'has_consumers': has_consumers
                    })
                except:
                    outputs.append({
                        'name': op.name,
                        'type': op.type,
                        'shape': "Unknown",
                        'dtype': "Unknown",
                        'output_tensor': None,
                        'has_consumers': has_consumers
                    })
    
    # Filter operations if requested
    filtered_ops = all_ops
    if filter_ops:
        filtered_ops = [op for op in all_ops if filter_ops.lower() in op['name'].lower()]
    
    return {
        'success': True,
        'model_path': model_path,
        'file_size': os.path.getsize(model_path),
        'total_operations': len(all_ops),
        'operation_types': op_types,
        'inputs': inputs,
        'potential_outputs': outputs,
        'all_operations': filtered_ops if show_all_ops or filter_ops else all_ops[:50],
        'truncated': not show_all_ops and not filter_ops and len(all_ops) > 50
    }


def _inspect_basic(model_path):
    """Basic inspection without TensorFlow"""
    try:
        # Try to parse the protobuf without TensorFlow
        with open(model_path, 'rb') as f:
            content = f.read()
        
        # Very basic analysis - just file info
        return {
            'success': True,
            'model_path': model_path,
            'file_size': len(content),
            'note': 'Limited inspection - install TensorFlow for detailed analysis',
            'inputs': [],
            'potential_outputs': [],
            'all_operations': [],
            'total_operations': 0
        }
    except Exception as e:
        raise Exception(f"Could not read model file: {e}")


def print_inspection_results(results):
    """Pretty print the inspection results"""
    
    if not results['success']:
        print(f"❌ Inspection failed: {results['error']}")
        return
    
    print("🔍 TensorFlow Model Inspection")
    print("=" * 60)
    print(f"📁 File: {results['model_path']}")
    print(f"📊 Size: {results['file_size']:,} bytes ({results['file_size']/1024/1024:.2f} MB)")
    
    if 'note' in results:
        print(f"ℹ️  Note: {results['note']}")
        return
    
    print(f"🔧 Total Operations: {results['total_operations']}")
    
    # Operation type summary
    if 'operation_types' in results:
        print(f"\n📋 Operation Types (top 10):")
        sorted_types = sorted(results['operation_types'].items(), key=lambda x: x[1], reverse=True)
        for i, (op_type, count) in enumerate(sorted_types[:10], 1):
            print(f"   {i:2d}. {op_type}: {count}")
        if len(sorted_types) > 10:
            print(f"   ... and {len(sorted_types) - 10} more types")
    
    # Input information
    print(f"\n📥 Model Inputs ({len(results['inputs'])}):")
    if results['inputs']:
        for i, inp in enumerate(results['inputs'], 1):
            print(f"   {i}. Name: {inp['name']}")
            print(f"      Shape: {inp['shape']}")
            print(f"      Type: {inp['dtype']}")
            if inp.get('output_tensor'):
                print(f"      Tensor: {inp['output_tensor']}")
            print()
    else:
        print("   No placeholder inputs found")
    
    # Output information
    print(f"📤 Potential Outputs ({len(results['potential_outputs'])}):")
    if results['potential_outputs']:
        for i, out in enumerate(results['potential_outputs'], 1):
            print(f"   {i}. Name: {out['name']}")
            print(f"      Type: {out['type']}")
            print(f"      Shape: {out['shape']}")
            if out.get('output_tensor'):
                print(f"      Tensor: {out['output_tensor']}")
            print(f"      Has Consumers: {out.get('has_consumers', 'Unknown')}")
            print()
    else:
        print("   No obvious output operations found")
    
    # Sample operations
    ops_to_show = results['all_operations']
    if ops_to_show:
        print(f"🔧 Operations:")
        if results.get('truncated'):
            print(f"   (Showing first 50 of {results['total_operations']} operations)")
        
        for i, op in enumerate(ops_to_show[:20], 1):
            inputs_info = f" ({op['input_count']} inputs)" if op['input_count'] > 0 else ""
            outputs_info = f" → {op['output_count']} outputs" if op['output_count'] > 0 else ""
            print(f"   {i:2d}. {op['name']} ({op['type']}){inputs_info}{outputs_info}")
            
            # Show shapes if available
            if 'output_shapes' in op and op['output_shapes']:
                for j, (shape, dtype) in enumerate(zip(op['output_shapes'], op.get('output_dtypes', []))):
                    if shape != "Unknown":
                        print(f"       Output {j}: {shape} ({dtype})")
        
        if len(ops_to_show) > 20:
            print(f"   ... and {len(ops_to_show) - 20} more operations")
    
    # Helpful suggestions
    print(f"\n💡 DeepRacer Model Conversion Tips:")
    
    if results['inputs']:
        print(f"   • Found {len(results['inputs'])} input(s)")
        for inp in results['inputs']:
            if 'observation' in inp['name'].lower():
                print(f"   • Camera input detected: {inp['name']}")
            elif 'lidar' in inp['name'].lower():
                print(f"   • LiDAR input detected: {inp['name']}")
    
    policy_outputs = [out for out in results['potential_outputs'] if 'policy' in out['name']]
    if policy_outputs:
        print(f"   • Found {len(policy_outputs)} policy output(s)")
        for out in policy_outputs:
            print(f"     - {out['name']}")
    
    if 'main_level/agent' in str(results):
        print(f"   • DeepRacer network structure detected")
    
    print(f"   • Use --show-all to see all operations")
    print(f"   • Use --filter <pattern> to search for specific operations")


def main():
    """Main function for command-line usage"""
    
    parser = argparse.ArgumentParser(
        description="Inspect TensorFlow model files and display their structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 model_inspector.py model.pb
  python3 model_inspector.py model.pb --show-all
  python3 model_inspector.py model.pb --filter observation
        """
    )
    
    parser.add_argument(
        "model_path",
        help="Path to TensorFlow model file (.pb)"
    )
    
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Show all operations (can be very long)"
    )
    
    parser.add_argument(
        "--filter",
        help="Filter operations by name pattern"
    )
    
    args = parser.parse_args()
    
    # Validate file exists
    if not os.path.isfile(args.model_path):
        print(f"❌ Error: Model file not found: {args.model_path}")
        sys.exit(1)
    
    # Perform inspection
    print("🔄 Inspecting model...")
    results = inspect_tensorflow_model(
        args.model_path, 
        show_all_ops=args.show_all,
        filter_ops=args.filter
    )
    
    # Print results
    print_inspection_results(results)
    
    if results['success']:
        print(f"\n✅ Inspection completed successfully")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()